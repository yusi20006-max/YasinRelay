"""
integration.py
لایه ادغام (Integration Layer) و زیرساخت آماده‌سازی افزونه‌ها (Plugin Preparation) برای YasinRelay.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional

from .ai_processor import ContentProcessor
from .eitaa_publisher import EitaaPublisher
from .fetch_engine import FetchEngine
from .media_processor import MediaProcessor

logger = logging.getLogger(__name__)


class IntegrationPlugin(ABC):
    """رابط پایه انتزاعی برای تمامی پلاگین‌ها و یکپارچه‌سازی‌های خارجی YasinRelay."""

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """نام منحصربه‌فرد افزونه/پلاگین."""
        raise NotImplementedError

    @abstractmethod
    def initialize(self, event_bus: Any) -> None:
        """راه‌اندازی اولیه افزونه و متصل کردن شنونده‌های رویدادها (Event Listeners)."""
        raise NotImplementedError


class IntegrationRegistry:
    """ثبت‌کننده مرکزی برای پلاگین‌ها، ارائه‌دهندگان هوش مصنوعی، منابع فید و ناشران سفارشی."""

    def __init__(self) -> None:
        self._ai_providers: Dict[str, Type[ContentProcessor]] = {}
        self._feed_sources: Dict[str, Type[FetchEngine]] = {}
        self._publishers: Dict[str, Type[Any]] = {}
        self._media_processors: Dict[str, Type[MediaProcessor]] = {}
        self._plugins: Dict[str, IntegrationPlugin] = {}

    def register_ai_provider(self, name: str, provider_cls: Optional[Type[ContentProcessor]] = None) -> Any:
        """ثبت یک ارائه‌دهنده هوش مصنوعی جدید (پشتیبانی از دکوراتور و فراخوانی مستقیم)."""
        if provider_cls is None:
            def decorator(cls: Type[ContentProcessor]) -> Type[ContentProcessor]:
                self._ai_providers[name] = cls
                logger.info(f"[IntegrationRegistry] ارائه‌دهنده هوش مصنوعی جدید ثبت شد (دکوراتور): {name}")
                return cls
            return decorator

        self._ai_providers[name] = provider_cls
        logger.info(f"[IntegrationRegistry] ارائه‌دهنده هوش مصنوعی جدید ثبت شد: {name}")
        return provider_cls

    def register_feed_source(self, name: str, source_cls: Optional[Type[FetchEngine]] = None) -> Any:
        """ثبت یک منبع دریافت فید جدید (پشتیبانی از دکوراتور و فراخوانی مستقیم)."""
        if source_cls is None:
            def decorator(cls: Type[FetchEngine]) -> Type[FetchEngine]:
                self._feed_sources[name] = cls
                logger.info(f"[IntegrationRegistry] منبع دریافت فید جدید ثبت شد (دکوراتور): {name}")
                return cls
            return decorator

        self._feed_sources[name] = source_cls
        logger.info(f"[IntegrationRegistry] منبع دریافت فید جدید ثبت شد: {name}")
        return source_cls

    def register_publisher(self, name: str, publisher_cls: Optional[Type[Any]] = None) -> Any:
        """ثبت یک ناشر جدید (پشتیبانی از دکوراتور و فراخوانی مستقیم)."""
        if publisher_cls is None:
            def decorator(cls: Type[Any]) -> Type[Any]:
                self._publishers[name] = cls
                logger.info(f"[IntegrationRegistry] ناشر جدید ثبت شد (دکوراتور): {name}")
                return cls
            return decorator

        self._publishers[name] = publisher_cls
        logger.info(f"[IntegrationRegistry] ناشر جدید ثبت شد: {name}")
        return publisher_cls

    def register_media_processor(self, name: str, processor_cls: Optional[Type[MediaProcessor]] = None) -> Any:
        """ثبت یک پردازشگر رسانه جدید (پشتیبانی از دکوراتور و فراخوانی مستقیم)."""
        if processor_cls is None:
            def decorator(cls: Type[MediaProcessor]) -> Type[MediaProcessor]:
                self._media_processors[name] = cls
                logger.info(f"[IntegrationRegistry] پردازشگر رسانه جدید ثبت شد (دکوراتور): {name}")
                return cls
            return decorator

        self._media_processors[name] = processor_cls
        logger.info(f"[IntegrationRegistry] پردازشگر رسانه جدید ثبت شد: {name}")
        return processor_cls

    def register_plugin(self, name: str, plugin_instance: IntegrationPlugin) -> IntegrationPlugin:
        """ثبت و مقداردهی اولیه یک پلاگین/افزونه کامل."""
        self._plugins[name] = plugin_instance
        logger.info(f"[IntegrationRegistry] افزونه جدید ثبت شد: {name}")
        return plugin_instance

    def get_ai_provider(self, name: str) -> Optional[Type[ContentProcessor]]:
        """دریافت کلاس پردازشگر هوش مصنوعی بر اساس نام."""
        return self._ai_providers.get(name)

    def get_feed_source(self, name: str) -> Optional[Type[FetchEngine]]:
        """دریافت کلاس موتور دریافت فید بر اساس نام."""
        return self._feed_sources.get(name)

    def get_publisher(self, name: str) -> Optional[Type[Any]]:
        """دریافت کلاس ناشر بر اساس نام."""
        return self._publishers.get(name)

    def get_media_processor(self, name: str) -> Optional[Type[MediaProcessor]]:
        """دریافت کلاس پردازشگر رسانه بر اساس نام."""
        return self._media_processors.get(name)

    def get_plugin(self, name: str) -> Optional[IntegrationPlugin]:
        """دریافت شیء افزونه بر اساس نام."""
        return self._plugins.get(name)

    def list_plugins(self) -> Dict[str, IntegrationPlugin]:
        """برگرداندن لیست تمام افزونه‌های ثبت شده."""
        return dict(self._plugins)


# ایجاد نمونه یکتا از رجیستری برای کل سیستم جهت تعامل آسان
integration_registry = IntegrationRegistry()
