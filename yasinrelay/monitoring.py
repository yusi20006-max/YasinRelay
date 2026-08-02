"""
monitoring.py
سیستم مانیتورینگ ران‌تایم و گزارش سلامت برای هسته YasinRelay.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .config import load_config
from .storage.database import Database
from .event_bus import (
    get_event_bus,
    EVENT_CONTENT_RECEIVED,
    EVENT_PUBLISHING_COMPLETED,
    EVENT_PROCESSING_FAILED,
    PipelineEvent,
)

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    کلاس مانیتورینگ سلامت ران‌تایم و آمارهای عملکردی رله.
    این کلاس به صورت موازی رویدادهای EventBus را مانیتور کرده و وضعیت ارتباطات و سنجه‌ها را گزارش می‌کند.
    """

    def __init__(self) -> None:
        self.start_time = datetime.now(timezone.utc)
        self.last_run_time: Optional[datetime] = None
        self._lock = threading.Lock()

        # سنجه‌های در حال اجرا (In-Memory Metrics)
        self.total_fetched_posts = 0
        self.total_published_posts = 0
        self.total_failed_posts = 0

        # ردیابی آخرین خطای رخ‌داده
        self.last_error_message: Optional[str] = None
        self.last_error_time: Optional[datetime] = None

    def on_event(self, event: PipelineEvent) -> None:
        """
        دریافت رویدادهای پایپ‌لاین برای به‌روزرسانی آمارهای لحظه‌ای.
        """
        with self._lock:
            self.last_run_time = datetime.now(timezone.utc)

            if event.name == EVENT_CONTENT_RECEIVED:
                self.total_fetched_posts += 1
            elif event.name == EVENT_PUBLISHING_COMPLETED:
                self.total_published_posts += 1
            elif event.name == EVENT_PROCESSING_FAILED:
                self.total_failed_posts += 1
                errors = event.payload.get("errors", [])
                if errors:
                    self.last_error_message = errors[-1]
                else:
                    self.last_error_message = "Unknown error during processing"
                self.last_error_time = datetime.now(timezone.utc)

    def get_health_report(self, database: Optional[Database] = None) -> Dict[str, Any]:
        """
        تولید گزارش جامع سلامت و عملکرد ران‌تایم رله.
        """
        config = load_config()
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        # ۱. بررسی سلامت پایگاه‌داده SQLite
        db = database
        db_created_internally = False
        if db is None:
            try:
                db = Database(config.database_path)
                db_created_internally = True
            except Exception as e:
                logger.error(f"[Monitoring] خطا در راه‌اندازی دیتابیس برای گزارش سلامت: {e}")

        db_status = "connected"
        db_err = None
        db_counts = {"total_posts": 0, "published_posts": 0, "pending_posts": 0, "failed_posts": 0}

        if db is not None:
            try:
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()

                cursor.execute("SELECT COUNT(*) FROM posts")
                db_counts["total_posts"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'published'")
                db_counts["published_posts"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'pending'")
                db_counts["pending_posts"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'failed'")
                db_counts["failed_posts"] = cursor.fetchone()[0]
            except Exception as e:
                db_status = "error"
                db_err = str(e)
            finally:
                if db_created_internally:
                    try:
                        db.close()
                    except Exception:
                        pass
        else:
            db_status = "error"
            db_err = "Database connection object is None"

        # ۲. بررسی باینری Fetcher
        # به طور پیش‌فرض مسیر باینری در "./fetcher/openfeed-fetch" قرار دارد
        fetcher_binary = "./fetcher/openfeed-fetch"
        fetcher_status = "available"
        fetcher_err = None
        if not Path(fetcher_binary).exists():
            fetcher_status = "unavailable"
            fetcher_err = f"Binary {fetcher_binary} not found on disk"

        # ۳. بررسی اتصال به ایتا (Publisher)
        publisher_status = "connected"
        publisher_err = None
        if not config.eitaa.token:
            publisher_status = "degraded"
            publisher_err = "Eitaa token is not configured"
        else:
            try:
                # ارسال یک درخواست HEAD سریع به وب‌سایت یا API ایتا
                resp = requests.head(config.eitaa.api_base, timeout=2.0)
                # در صورتی که پاسخ بدون استثنا برگردد، هاست در دسترس است
            except Exception as e:
                publisher_status = "error"
                publisher_err = f"Failed to connect to Eitaa API: {e}"

        # ۴. محاسبه نرخ خطا و وضعیت کلی سلامت سیستم
        with self._lock:
            total_processed = self.total_published_posts + self.total_failed_posts
            error_rate = 0.0
            if total_processed > 0:
                error_rate = (self.total_failed_posts / total_processed) * 100.0

            # اگر پایگاه‌داده دچار خطا باشد وضعیت کل سیستم error است.
            # اگر ارتباط با ایتا قطع باشد یا باینری فچر مفقود باشد وضعیت degraded است.
            overall_status = "active"
            if db_status == "error":
                overall_status = "error"
            elif fetcher_status == "unavailable" or publisher_status == "error" or error_rate > 50.0:
                overall_status = "degraded"

            report = {
                "status": overall_status,
                "uptime_seconds": int(uptime),
                "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
                "metrics": {
                    "total_fetched_posts": self.total_fetched_posts,
                    "total_published_posts": self.total_published_posts,
                    "total_failed_posts": self.total_failed_posts,
                    "error_rate_percent": round(error_rate, 2),
                },
                "connections": {
                    "database": {
                        "status": db_status,
                        "error_message": db_err
                    },
                    "fetcher": {
                        "status": fetcher_status,
                        "binary_path": fetcher_binary,
                        "error_message": fetcher_err
                    },
                    "publisher": {
                        "status": publisher_status,
                        "api_base": config.eitaa.api_base,
                        "error_message": publisher_err
                    }
                },
                "db_stats": db_counts,
                "last_error": {
                    "message": self.last_error_message,
                    "timestamp": self.last_error_time.isoformat() if self.last_error_time else None
                } if self.last_error_message else None
            }
            return report


_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """
    دریافت کلاینت سینگلتون HealthMonitor و عضویت در EventBus محلی.
    """
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
        try:
            get_event_bus().subscribe("*", _health_monitor.on_event)
        except Exception as e:
            logger.error(f"[Monitoring] خطا در عضویت مانیتورینگ سلامت در EventBus: {e}")
    return _health_monitor
