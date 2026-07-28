"""
media_processor.py
رابط پردازش رسانه‌ها (تصویر، ویدیو، سند).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MediaProcessor(ABC):
    """رابط اصلی پردازشگرهای رسانه."""

    @abstractmethod
    def process_image(self, media_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        """پردازش تصویر و بازگرداندن آدرس تصویر نهایی یا بهینه‌شده."""
        raise NotImplementedError

    @abstractmethod
    def process_video(self, media_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        """پردازش ویدیو و بازگرداندن آدرس ویدیوی نهایی یا بهینه‌شده."""
        raise NotImplementedError

    @abstractmethod
    def process_document(self, media_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        """پردازش فایل/سند و بازگرداندن آدرس نهایی."""
        raise NotImplementedError


class PassthroughMediaProcessor(MediaProcessor):
    """پیاده‌سازی پیش‌فرض/عبوردهنده بدون اعمال تغییر روی رسانه‌ها."""

    def process_image(self, media_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        return media_url

    def process_video(self, media_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        return media_url

    def process_document(self, media_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        return media_url
