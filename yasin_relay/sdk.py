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
            # بررسی دسترسی دیتابیس با وجود داشتن پست آزمایشی یا ساختار معتبر جدول
            self._db.exists("test_source", "test_id")
            return True
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
            except Exception:
                pass

            # محاسبه تعداد پست‌های پردازش شده و ارسال شده از پایگاه‌داده
            total_posts = 0
            published_posts = 0
            try:
                conn = self._db._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM posts")
                total_posts = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'published'")
                published_posts = cursor.fetchone()[0]
            except Exception:
                pass

            return {
                "status": "active" if is_running else "idle",
                "active_rules": len(self._config.source_channels),
                "processed_messages": total_posts,
                "published_messages": published_posts,
                "source_channels": self._config.source_channels,
                "destination_channel": self._config.eitaa.channel,
            }
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
