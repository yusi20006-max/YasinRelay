"""
base.py
تعریف کلاس‌های پایه و رابط‌های استاندارد (Interfaces) برای سیستم پلاگین‌های YasinRelay.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from yasinrelay.fetch_engine import FetchEngine, Post
from yasinrelay.ai_processor import ContentProcessor, ProcessedContent
from yasinrelay.media_processor import MediaProcessor
from yasinrelay.eitaa_publisher import PublishResult


class BasePlugin(ABC):
    """کلاس پایه برای تمام افزونه‌ها در YasinRelay."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None) -> None:
        self.settings: Dict[str, Any] = settings or {}
        self.enabled: bool = True

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """شناسه منحصربه‌فرد افزونه (مانند custom_ai_processor)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """نام خوانای افزونه."""
        raise NotImplementedError

    @property
    def version(self) -> str:
        """نسخه افزونه."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """توضیح کوتاه درباره کارکرد افزونه."""
        return ""

    def initialize(self, event_bus: Any, registry: Any) -> None:
        """راه‌اندازی افزونه، عضویت در رویدادها و ثبت در رجیستری یکپارچه‌سازی."""
        pass

    def shutdown(self) -> None:
        """کارهای پاک‌سازی افزونه در زمان غیرفعال‌سازی یا خاموش شدن سیستم."""
        pass


class SourcePlugin(BasePlugin, FetchEngine):
    """رابط افزونه‌های فید و دریافت اطلاعات (Source Plugins)."""

    @abstractmethod
    def fetch(self, channel: str, limit: int = 10) -> List[Post]:
        """دریافت لیست پست‌ها از منبع سفارشی."""
        raise NotImplementedError


class AIPlugin(BasePlugin, ContentProcessor):
    """رابط افزونه‌های پردازشگر هوش مصنوعی (AI Plugins)."""

    @abstractmethod
    def process(self, post: Post) -> ProcessedContent:
        """پردازش و تحلیل پست به همراه اعمال تغییرات هوش مصنوعی سفارشی."""
        raise NotImplementedError


class MediaPlugin(BasePlugin, MediaProcessor):
    """رابط افزونه‌های پیش‌پردازش رسانه و تصویر (Media Plugins)."""

    @abstractmethod
    def process_image(self, url: str) -> str:
        """پردازش یا ویرایش تصویر (مانند افزودن واترمارک) و برگرداندن URL جدید."""
        raise NotImplementedError


class PublisherPlugin(BasePlugin):
    """رابط افزونه‌های انتشار محتوا در پلتفرم‌های خارجی (Publisher Plugins)."""

    @abstractmethod
    def publish(self, content: ProcessedContent) -> PublishResult:
        """انتشار پست نهایی در شبکه یا پلتفرم مقصد."""
        raise NotImplementedError
