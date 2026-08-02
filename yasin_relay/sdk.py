"""
sdk.py
SDK عمومی YasinRelay جهت تعامل با YasinHub و اکوسیستم یاسین.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict, Optional

from yasinrelay.config import load_config
from yasinrelay.storage.database import Database
from yasinrelay.event_bus import get_event_bus, PipelineEvent

logger = logging.getLogger(__name__)


class YasinRelayClient:
    """
    کلاینت عمومی YasinRelay برای برقراری ارتباط با YasinHub و مانیتورینگ وضعیت.
    """

    def __init__(self) -> None:
        self._config = load_config()
        self._db = Database(self._config.database_path)
        self._event_bus = get_event_bus()

    def connect(self) -> bool:
        """
        برقراری ارتباط با سرویس رله.
        در اینجا با بررسی و تایید دسترسی به پایگاه‌داده و معتبر بودن تنظیمات، وضعیت اتصال را تایید می‌کنیم.
        """
        try:
            conn = self._db._get_connection()
            try:
                conn.execute("SELECT 1")
                return True
            finally:
                if self._db._conn is None:
                    conn.close()
        except Exception as e:
            logger.error(f"Error connecting to YasinRelay: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        دریافت وضعیت و آمارهای عملکردی سرویس رله.
        """
        try:
            # بررسی در حال اجرا بودن پروسس رله با pgrep
            # الگوی جستجوی پروسس منطبق با yasinrelay.cli است
            is_running = False
            try:
                res = subprocess.run(["pgrep", "-f", "yasinrelay.cli"], capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    is_running = True
            except Exception as e:
                logger.debug(f"Pgrep check failed (possibly unsupported platform/permissions): {e}")

            # دریافت گزارش سلامت جامع از لایه مانیتورینگ
            from yasinrelay.monitoring import get_health_monitor
            monitor = get_health_monitor()
            report = monitor.get_health_report(self._db)

            # ادغام و حفظ سازگاری کامل با کلیدهای قدیمی
            # برای حفظ سازگاری ۱۰۰٪ با کلید status قدیمی، وضعیت دقیقاً "active" در صورت در حال اجرا بودن پروسس و "idle" در غیر این صورت بازگردانده می‌شود.
            # اطلاعات تفصیلی و داینامیک سلامت (از جمله active, degraded, error) در ساختار جدید health قرار دارد.
            status_val = "active" if is_running else "idle"

            result = {
                "status": status_val,
                "active_rules": len(self._config.source_channels),
                "processed_messages": report["db_stats"]["total_posts"],
                "published_messages": report["db_stats"]["published_posts"],
                "source_channels": self._config.source_channels,
                "destination_channel": self._config.eitaa.channel,
                "health": report,
                "uptime_seconds": report["uptime_seconds"],
                "last_run_time": report["last_run_time"],
                "metrics": report["metrics"],
                "connections": report["connections"],
                "db_stats": report["db_stats"],
                "last_error": report["last_error"],
            }
            return result
        except Exception as e:
            logger.error(f"Error getting YasinRelay status: {e}")
            return {"status": "error", "error": str(e)}

    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        پردازش رویدادهای ارسالی از سمت اکوسیستم.
        این متد رویداد دریافتی را به سیستم Event Bus محلی YasinRelay ارسال می‌کند.
        """
        try:
            event = PipelineEvent(
                name=event_type,
                content_id=payload.get("content_id", "external_event"),
                payload=payload
            )
            self._event_bus.publish(event)
            return True
        except Exception as e:
            logger.error(f"Error handling external event '{event_type}': {e}")
            return False
