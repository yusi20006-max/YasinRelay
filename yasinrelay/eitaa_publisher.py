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

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from .ai_processor import ProcessedContent
from .config import EitaaConfig

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    success: bool
    response_body: Optional[str] = None
    error: Optional[str] = None


class PublishError(Exception):
    """خطای مربوط به انتشار در ایتا."""


def is_safe_url(url: str) -> bool:
    """بررسی امن بودن و معتبر بودن URL رسانه."""
    if not url:
        return False
    url_stripped = url.strip()
    # شروع با طرحواره مجاز
    if not (url_stripped.startswith("http://") or url_stripped.startswith("https://")):
        return False
    # عدم شروع با خط فاصله برای جلوگیری از آرگومان‌های تزریقی
    if url_stripped.startswith("-"):
        return False
    # عدم وجود کاراکترهای خطرناک تزریق دستور
    invalid_chars = [";", "|", "&", "$", "`", "\n", "\r", "<", ">"]
    if any(char in url_stripped for char in invalid_chars):
        return False

    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url_stripped)
        if not parsed.scheme or not parsed.netloc:
            return False
        return True
    except Exception:
        return False


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

        files = None
        if media_url:
            # بررسی صحت و امنیت آدرس قبل از فراخوانی فچر
            if not is_safe_url(media_url):
                logger.warning(f"Media URL {media_url} is unsafe or invalid, falling back to using URL as text payload")
                payload["file"] = media_url
            else:
                # Try to download actual file bytes using openfeed-fetch download subcommand
                try:
                    import subprocess
                    from pathlib import Path
                    binary_path = "./fetcher/openfeed-fetch"
                    if Path(binary_path).exists():
                        logger.info(f"Downloading media via telemirror: {media_url}")
                        res = subprocess.run(
                            [binary_path, "download", "--url", media_url.strip()],
                            capture_output=True,
                            check=True,
                            timeout=30
                        )
                        file_bytes = res.stdout
                        if file_bytes:
                            # Determine a file name (e.g. image.jpg)
                            file_name = "image.jpg"
                            # Extract extension from url if possible
                            if "." in media_url.split("/")[-1]:
                                potential_name = media_url.split("/")[-1].split("?")[0]
                                if len(potential_name) > 3:
                                    file_name = potential_name

                            # Guess mime type or use image/jpeg
                            mime_type = "image/jpeg"
                            if file_name.endswith(".png"):
                                mime_type = "image/png"
                            elif file_name.endswith(".gif"):
                                mime_type = "image/gif"
                            elif file_name.endswith(".mp4"):
                                mime_type = "video/mp4"

                            files = {
                                "file": (file_name, file_bytes, mime_type)
                            }
                        else:
                            logger.warning("Downloaded empty file bytes, falling back to URL")
                            payload["file"] = media_url
                    else:
                        logger.warning(f"Binary {binary_path} not found, falling back to URL")
                        payload["file"] = media_url
                except Exception as e:
                    logger.error(f"Failed to download media via telemirror: {e}, falling back to URL", exc_info=True)
                    payload["file"] = media_url

        try:
            response = requests.post(url, data=payload, files=files, timeout=30)
            self._last_publish_time = time.time()
        except requests.RequestException as exc:
            raise PublishError(f"ارتباط با API ایتایار برقرار نشد: {exc}") from exc

        if response.status_code != 200:
            return PublishResult(success=False, response_body=response.text, error=f"HTTP {response.status_code}")

        try:
            # بررسی پاسخ JSON برای تشخیص ردهای صریح از طرف سرور ایتا
            data = response.json()
            if isinstance(data, dict) and not data.get("ok", True):
                error_msg = data.get("description") or "API returned ok=false"
                return PublishResult(success=False, response_body=response.text, error=error_msg)
        except Exception:
            # در صورتی که پاسخ JSON نبود، به فرض موفق بودن بر اساس کد 200 تکیه می‌کنیم
            pass

        return PublishResult(success=True, response_body=response.text)
