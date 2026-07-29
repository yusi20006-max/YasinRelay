"""
config.py
بارگذاری تنظیمات از متغیرهای محیطی (.env) — بدون هاردکد کردن توکن‌ها.

تنظیمات توسعه‌یافته برای نسخه ۲ هسته YasinRelay.
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
    database_path: str = "relay.db"
    log_level: str = "INFO"
    schedule_interval: int = 1800  # ۳۰ دقیقه به عنوان مقدار پیش‌فرض
    ai_provider: str = "passthrough"
    event_bus_enabled: bool = True
    event_logging_enabled: bool = True


def load_config() -> RelayConfig:
    token = os.environ.get("EITAA_TOKEN", "")
    channel = os.environ.get("EITAA_CHANNEL", "")
    sources_raw = os.environ.get("SOURCE_CHANNELS", "")
    sources = [s.strip() for s in sources_raw.split(",") if s.strip()]

    # دریافت متغیرهای محیطی جدید با مقادیر پیش‌فرض
    database_path = os.environ.get("DATABASE_PATH", "relay.db")
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    # برای سازگاری کامل، مقدار پیش‌فرض SCHEDULE_INTERVAL ابتدا از FETCH_INTERVAL_SECONDS استفاده می‌کند
    fetch_interval = int(os.environ.get("FETCH_INTERVAL_SECONDS", "3600"))
    schedule_interval_raw = os.environ.get("SCHEDULE_INTERVAL")
    if schedule_interval_raw is not None:
        schedule_interval = int(schedule_interval_raw)
    else:
        schedule_interval = fetch_interval

    ai_provider = os.environ.get("AI_PROVIDER", "passthrough")

    # رویدادها و گذرگاه رویداد داخلی
    event_bus_enabled = os.environ.get("EVENT_BUS_ENABLED", "true").lower() in ("true", "1", "yes")
    event_logging_enabled = os.environ.get("EVENT_LOGGING_ENABLED", "true").lower() in ("true", "1", "yes")

    return RelayConfig(
        eitaa=EitaaConfig(token=token, channel=channel),
        source_channels=sources,
        fetch_interval_seconds=fetch_interval,
        inter_message_delay_seconds=int(os.environ.get("INTER_MESSAGE_DELAY_SECONDS", "15")),
        ai_api_key=os.environ.get("AI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
        ai_base_url=os.environ.get("AI_BASE_URL", "https://api.openai.com/v1"),
        ai_model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
        database_path=database_path,
        log_level=log_level,
        schedule_interval=schedule_interval,
        ai_provider=ai_provider,
        event_bus_enabled=event_bus_enabled,
        event_logging_enabled=event_logging_enabled,
    )
