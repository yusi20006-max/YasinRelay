"""
scheduler.py
زمان‌بند سبک و بدون نیاز به کتابخانه‌های سنگین خارجی برای اجرای دوره‌ای پایپ‌لاین.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


class Scheduler:
    """زمان‌بند سبک برای اجرای یک تابع به صورت دوره‌ای."""

    def __init__(self, interval_seconds: int, task: Callable[[], None]) -> None:
        self.interval_seconds = max(1, interval_seconds)
        self.task = task
        self._running = False

    def start(self) -> None:
        """شروع اجرای زمان‌بند."""
        self._running = True
        logger.info(f"شروع زمان‌بند با بازه زمانی: {self.interval_seconds} ثانیه")
        try:
            while self._running:
                logger.info("شروع اجرای تسک زمان‌بندی شده...")
                try:
                    self.task()
                except Exception as exc:
                    logger.error(f"خطا در اجرای تسک زمان‌بندی شده: {exc}", exc_info=True)

                logger.info(f"پایان اجرای تسک. خوابیدن به مدت {self.interval_seconds} ثانیه...")

                # خوابیدن در بازه‌های کوچک ۱ ثانیه‌ای برای پاسخگویی سریع‌تر به سیگنال توقف
                elapsed = 0
                while elapsed < self.interval_seconds and self._running:
                    time.sleep(1)
                    elapsed += 1
        except KeyboardInterrupt:
            logger.info("زمان‌بند با درخواست کاربر (KeyboardInterrupt) متوقف شد.")
        finally:
            self._running = False

    def stop(self) -> None:
        """متوقف کردن زمان‌بند."""
        self._running = False
        logger.info("زمان‌بند متوقف شد.")
