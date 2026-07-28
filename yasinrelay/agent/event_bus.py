"""
event_bus.py
سیستم توزیع رویداد سبک (Event Bus) مبتنی بر کتابخانه استاندارد پایتون.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

# رویدادهای پیش‌فرض سیستم (Built-in events)
TASK_STARTED = "TaskStarted"
TASK_FINISHED = "TaskFinished"
TASK_FAILED = "TaskFailed"
TOOL_STARTED = "ToolStarted"
TOOL_FINISHED = "ToolFinished"
RETRY_STARTED = "RetryStarted"
RETRY_FINISHED = "RetryFinished"
STATE_CHANGED = "StateChanged"


class EventBus:
    """سیستم سبک انتشار/اشتراک (Pub-Sub) برای رویدادها."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[..., Any]]] = {}

    def subscribe(self, event_name: str, callback: Callable[..., Any]) -> None:
        """عضویت در یک رویداد خاص."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)
            logger.debug(f"شنونده جدید برای رویداد {event_name} ثبت شد.")

    def unsubscribe(self, event_name: str, callback: Callable[..., Any]) -> None:
        """لغو عضویت از یک رویداد خاص."""
        if event_name in self._listeners:
            if callback in self._listeners[event_name]:
                self._listeners[event_name].remove(callback)
                logger.debug(f"شنونده از رویداد {event_name} حذف شد.")

    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """انتشار یک رویداد به تمام شنوندگان ثبت‌شده."""
        if event_name in self._listeners:
            # ایجاد یک کپی از لیست برای جلوگیری از تداخل در صورتی که شنونده خودش را غیرفعال کند
            listeners_copy = list(self._listeners[event_name])
            for callback in listeners_copy:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"خطا در اجرای تابع بازگشتی رویداد {event_name}: {e}",
                        exc_info=True,
                    )
