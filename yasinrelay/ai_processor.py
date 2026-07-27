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
    """
    پردازشگر هوش مصنوعی واقعی که محتوای پست را با استفاده از API ارتقا یا ترجمه می‌دهد.
    در صورتی که کلید API (AI_API_KEY) تنظیم نشده باشد یا خطا رخ دهد، متن را بدون تغییر عبور می‌دهد.
    """

    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def process(self, post: Post) -> ProcessedContent:
        if not self.api_key:
            return ProcessedContent(source_post=post, text=post.text)

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            "You are a professional content editor for Iranian social media channels (specifically Eitaa).\n"
            "Your task is to rewrite, translate (if in another language), or improve the following Telegram post "
            "to make it engaging, polished, and suitable for Iranian audiences. Keep emojis, layout, and meaning intact. "
            "Output ONLY the final processed text, with no introductory or concluding remarks.\n\n"
            f"Post content:\n{post.text}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        try:
            import requests
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                result = response.json()
                processed_text = result["choices"][0]["message"]["content"].strip()
                return ProcessedContent(source_post=post, text=processed_text)
            else:
                print(f"AI API returned error {response.status_code}: {response.text}")
        except Exception as exc:
            print(f"Failed to process content with AI: {exc}")

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
