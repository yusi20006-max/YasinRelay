"""
eitaa_publisher.py
انتشار محتوای پردازش‌شده در کانال ایتا از طریق API ایتایار.

نکات فنی که قبلاً در پروژه‌ی eitaa_news_v2 کشف شده و اینجا هم رعایت
شده‌اند:
  - دامنه‌ی صحیح API: eitaayar.ir/api/ (نه api.eitaa.com)
  - endpoint فایل: sendFile ، endpoint متن: sendMessage
  - بدون پیشوند تکراری "bot" در توکن
  - تأخیر بین پیام‌ها برای جلوگیری از rate-limit / ارسال انبوه ناخواسته
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from .ai_processor import ProcessedContent
from .config import EitaaConfig


@dataclass
class PublishResult:
    success: bool
    response_body: Optional[str] = None
    error: Optional[str] = None


class PublishError(Exception):
    """خطای مربوط به انتشار در ایتا."""


class EitaaPublisher:
    def __init__(self, config: EitaaConfig, inter_message_delay_seconds: int = 15) -> None:
        self._config = config
        self._delay = inter_message_delay_seconds
        self._last_publish_time: Optional[float] = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_publish_time is None:
            return
        elapsed = time.time() - self._last_publish_time
        remaining = self._delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def publish(self, content: ProcessedContent) -> PublishResult:
        self._wait_for_rate_limit()

        token = self._config.token
        if not token:
            raise PublishError("EITAA_TOKEN تنظیم نشده است")

        media_url = content.source_post.media_url
        endpoint = "sendFile" if media_url else "sendMessage"
        url = f"{self._config.api_base}{token}/{endpoint}"

        payload = {
            "chat_id": self._config.channel,
            "text": content.text,
        }
        if media_url:
            payload["file"] = media_url

        try:
            response = requests.post(url, data=payload, timeout=30)
            self._last_publish_time = time.time()
        except requests.RequestException as exc:
            raise PublishError(f"ارتباط با API ایتایار برقرار نشد: {exc}") from exc

        if response.status_code != 200:
            return PublishResult(success=False, response_body=response.text, error=f"HTTP {response.status_code}")

        return PublishResult(success=True, response_body=response.text)
