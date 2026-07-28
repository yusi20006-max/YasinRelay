"""
fetch_engine.py
موتور دریافت محتوا از کانال‌های تلگرام.

طبق تصمیم معماری: منطق واقعی fetch (پکیج‌های Go گرفته‌شده از OpenFeed:
provider/telemirror با زنجیره‌ی TeleMirror -> Google -> GoogleTranslate
-> Direct) باید به‌صورت باینری کامپایل‌شده در `fetcher/` قرار بگیرد و
از طریق subprocess فراخوانی شود — بدون وابستگی runtime به یک نمونه‌ی
جداگانه‌ی در حال اجرای OpenFeed.

این ماژول یک FetchEngine انتزاعی تعریف می‌کند تا:
  - در توسعه/تست بتوان از FakeFetcher استفاده کرد (بدون نیاز به باینری Go)
  - در production از SubprocessFetcher واقعی استفاده شود
بدون این‌که بقیه‌ی pipeline (AI processor, publisher) چیزی درباره‌ی
پیاده‌سازی fetch بداند.
"""

from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Post:
    """یک پست دریافت‌شده از کانال منبع."""

    channel: str
    message_id: str
    text: str
    media_url: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class FetchError(Exception):
    """خطای مربوط به دریافت محتوا از منبع."""


class FetchEngine(ABC):
    """رابط پایه‌ی موتور دریافت — پیاده‌سازی‌ها باید این را extend کنند."""

    @abstractmethod
    def fetch(self, channel: str, limit: int = 10) -> List[Post]:
        """آخرین پست‌های یک کانال را برمی‌گرداند (جدیدترین اول)."""
        raise NotImplementedError


class SubprocessFetcher(FetchEngine):
    """
    فراخوانی باینری Go وندورشده (از OpenFeed) از طریق subprocess.

    انتظار می‌رود باینری در `binary_path` اجرا شود با آرگومان‌های:
        <binary> fetch --channel <channel> --limit <limit>
    و خروجی JSON با ساختار زیر روی stdout بدهد:
        [{"message_id": "...", "text": "...", "media_url": "..." }, ...]
    """

    def __init__(self, binary_path: str = "./fetcher/openfeed-fetch") -> None:
        self.binary_path = binary_path

    def fetch(self, channel: str, limit: int = 10) -> List[Post]:
        if not Path(self.binary_path).exists():
            raise FetchError(
                f"باینری fetcher پیدا نشد: {self.binary_path}. "
                "ابتدا کد Go وندورشده را داخل fetcher/ کامپایل کنید."
            )
        try:
            result = subprocess.run(
                [self.binary_path, "fetch", "--channel", channel, "--limit", str(limit)],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise FetchError(f"fetcher برای کانال '{channel}' شکست خورد: {exc.stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            raise FetchError(f"fetcher برای کانال '{channel}' timeout شد") from exc

        try:
            items = json.loads(result.stdout or "[]") or []
        except json.JSONDecodeError as exc:
            raise FetchError(f"خروجی fetcher برای '{channel}' JSON معتبر نبود") from exc

        return [
            Post(
                channel=channel,
                message_id=str(item.get("message_id", "")),
                text=item.get("text", ""),
                media_url=item.get("media_url"),
                raw=item,
            )
            for item in items
        ]


class FakeFetcher(FetchEngine):
    """
    پیاده‌سازی ساختگی برای تست و توسعه‌ی محلی — بدون نیاز به باینری Go.
    """

    def __init__(self, canned_posts: Optional[Dict[str, List[Post]]] = None) -> None:
        self._canned = canned_posts or {}

    def add_posts(self, channel: str, posts: List[Post]) -> None:
        self._canned.setdefault(channel, []).extend(posts)

    def fetch(self, channel: str, limit: int = 10) -> List[Post]:
        return list(self._canned.get(channel, []))[:limit]
