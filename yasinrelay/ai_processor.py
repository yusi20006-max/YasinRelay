"""
ai_processor.py
پردازش محتوای دریافت‌شده با AI: ترجمه، خلاصه‌سازی، بهبود متن.

پیاده‌سازی واقعی (فراخوانی API یک مدل زبانی) عمداً اینجا نیست — این
ماژول فقط یک رابط ساده (Processor) تعریف می‌کند تا بشه بعداً بک‌اند
دلخواه (Anthropic API، مدل محلی، و ...) رو بدون تغییر pipeline جایگزین
کرد.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional

from .fetch_engine import Post


@dataclass
class ProcessedContent:
    """خروجی پردازش‌شده‌ی یک Post، آماده برای انتشار."""

    source_post: Post
    text: str
    summary: Optional[str] = None


class ContentProcessor(ABC):
    """رابط پایه‌ی پردازشگر محتوا."""

    @abstractmethod
    def process(self, post: Post) -> ProcessedContent:
        raise NotImplementedError


class PassthroughProcessor(ContentProcessor):
    """پردازشگر ساده که متن را بدون تغییر عبور می‌دهد (برای تست/fallback)."""

    def process(self, post: Post) -> ProcessedContent:
        return ProcessedContent(source_post=post, text=post.text)


class CallableProcessor(ContentProcessor):
    """
    پردازشگری که یک تابع دلخواه (مثلاً فراخوانی یک API مدل زبانی) را
    اجرا می‌کند. تابع باید متن ورودی را بگیرد و متن پردازش‌شده را
    برگرداند — این‌طوری اتصال به هر backend ای (Anthropic API، مدل
    محلی و ...) بدون تغییر بقیه‌ی pipeline ممکن است.
    """

    def __init__(self, transform: Callable[[str], str]) -> None:
        self._transform = transform

    def process(self, post: Post) -> ProcessedContent:
        return ProcessedContent(source_post=post, text=self._transform(post.text))
