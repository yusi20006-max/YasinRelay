"""
event_bus.py
سیستم توزیع رویداد سبک (Event Bus) برای هسته و مراحل پایپ‌لاین YasinRelay.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config import load_config

logger = logging.getLogger(__name__)

# رویدادهای هسته (Core Events)
EVENT_CONTENT_RECEIVED = "ContentReceived"
EVENT_CONTENT_NORMALIZED = "ContentNormalized"
EVENT_DUPLICATE_DETECTED = "DuplicateDetected"
EVENT_PROCESSING_STARTED = "ProcessingStarted"
EVENT_AI_PROCESSING_COMPLETED = "AIProcessingCompleted"
EVENT_MEDIA_PROCESSING_COMPLETED = "MediaProcessingCompleted"
EVENT_PUBLISHING_STARTED = "PublishingStarted"
EVENT_PUBLISHING_COMPLETED = "PublishingCompleted"
EVENT_PROCESSING_FAILED = "ProcessingFailed"


@dataclass
class PipelineEvent:
    """ساختار استاندارد رویدادهای پایپ‌لاین."""

    name: str
    content_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """تبدیل رویداد به دیکشنری برای استفاده‌های خارجی یا لاگینگ."""
        return {
            "name": self.name,
            "content_id": self.content_id,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class EventBus:
    """سیستم سبک انتشار/اشتراک (Pub-Sub) برای مدیریت چرخه حیات رویدادهای پایپ‌لاین."""

    def __init__(self, enabled: bool = True, logging_enabled: bool = True) -> None:
        self.enabled = enabled
        self.logging_enabled = logging_enabled
        self._handlers: Dict[str, List[Callable[[PipelineEvent], None]]] = {}
        self._wildcard_handlers: List[Callable[[PipelineEvent], None]] = []

    def subscribe(self, event_name: str, handler: Callable[[PipelineEvent], None]) -> None:
        """عضویت و گوش دادن به یک رویداد خاص یا همه رویدادها (wildcard با '*')."""
        if event_name == "*":
            if handler not in self._wildcard_handlers:
                self._wildcard_handlers.append(handler)
                if self.logging_enabled:
                    logger.info("[EventBus] شنونده سراسری (Wildcard) جدید با موفقیت ثبت شد.")
        else:
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            if handler not in self._handlers[event_name]:
                self._handlers[event_name].append(handler)
                if self.logging_enabled:
                    logger.info(f"[EventBus] شنونده جدید برای رویداد '{event_name}' ثبت شد.")

    def unsubscribe(self, event_name: str, handler: Callable[[PipelineEvent], None]) -> None:
        """لغو عضویت یک شنونده از رویداد خاص یا سراسری."""
        if event_name == "*":
            if handler in self._wildcard_handlers:
                self._wildcard_handlers.remove(handler)
                if self.logging_enabled:
                    logger.info("[EventBus] شنونده سراسری (Wildcard) حذف شد.")
        else:
            if event_name in self._handlers and handler in self._handlers[event_name]:
                self._handlers[event_name].remove(handler)
                if self.logging_enabled:
                    logger.info(f"[EventBus] شنونده از رویداد '{event_name}' حذف شد.")

    def clear(self) -> None:
        """پاک‌سازی تمامی اشتراک‌ها (مدیریت چرخه حیات)."""
        self._handlers.clear()
        self._wildcard_handlers.clear()
        if self.logging_enabled:
            logger.info("[EventBus] تمامی اشتراک‌ها و هندلرها پاک‌سازی شدند.")

    def publish(self, event: PipelineEvent) -> None:
        """انتشار یک رویداد به تمامی هندلرهای متناظر و هندلرهای سراسری."""
        if not self.enabled:
            return

        if self.logging_enabled:
            logger.info(
                f"[EventBus] ایجاد و انتشار رویداد: '{event.name}' | "
                f"شناسه محتوا: '{event.content_id}' | زمان: {event.timestamp.isoformat()}"
            )

        # دریافت کپی از لیست هندلرها برای ایمنی در صورت تغییر پویا حین اجرا
        handlers_to_call: List[Callable[[PipelineEvent], None]] = []
        if event.name in self._handlers:
            handlers_to_call.extend(self._handlers[event.name])
        handlers_to_call.extend(self._wildcard_handlers)

        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception as exc:
                # شکست هندلر نباید پایپ‌لاین اصلی را متوقف کند
                logger.error(
                    f"[EventBus] خطا در اجرای شنونده برای رویداد '{event.name}' "
                    f"شناسه محتوا '{event.content_id}': {exc}",
                    exc_info=True,
                )


_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """دریافت نمونه یکتا و سراسری EventBus متناسب با تنظیمات سیستم."""
    global _global_event_bus
    if _global_event_bus is None:
        try:
            config = load_config()
            enabled = getattr(config, "event_bus_enabled", True)
            logging_enabled = getattr(config, "event_logging_enabled", True)
        except Exception:
            enabled = True
            logging_enabled = True
        _global_event_bus = EventBus(enabled=enabled, logging_enabled=logging_enabled)
    return _global_event_bus
