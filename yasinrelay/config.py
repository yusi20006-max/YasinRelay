"""
config.py
بارگذاری تنظیمات از متغیرهای محیطی (.env) — بدون هاردکد کردن توکن‌ها.

طبق تجربه‌ی قبلی پروژه‌های Yasin: توکن‌ها همیشه از dotenv خونده می‌شن،
هیچ‌وقت داخل کد نوشته نمی‌شن.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - در صورت نصب‌نبودن python-dotenv
    pass


@dataclass
class EitaaConfig:
    token: str
    channel: str
    api_base: str = "https://eitaayar.ir/api/"


@dataclass
class RelayConfig:
    eitaa: EitaaConfig
    source_channels: List[str]
    fetch_interval_seconds: int = 3600
    inter_message_delay_seconds: int = 15
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"


def load_config() -> RelayConfig:
    token = os.environ.get("EITAA_TOKEN", "")
    channel = os.environ.get("EITAA_CHANNEL", "")
    sources_raw = os.environ.get("SOURCE_CHANNELS", "")
    sources = [s.strip() for s in sources_raw.split(",") if s.strip()]

    return RelayConfig(
        eitaa=EitaaConfig(token=token, channel=channel),
        source_channels=sources,
        fetch_interval_seconds=int(os.environ.get("FETCH_INTERVAL_SECONDS", "3600")),
        inter_message_delay_seconds=int(os.environ.get("INTER_MESSAGE_DELAY_SECONDS", "15")),
        ai_api_key=os.environ.get("AI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
        ai_base_url=os.environ.get("AI_BASE_URL", "https://api.openai.com/v1"),
        ai_model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
    )
