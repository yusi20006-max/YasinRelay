"""
config.py
بارگذاری تنظیمات از متغیرهای محیطی و تنظیمات تعاملی پایدار.

تنظیمات توسعه‌یافته برای نسخه ۲ هسته YasinRelay.
"""

from __future__ import annotations

import getpass
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - در صورت نصب‌نبودن python-dotenv
    pass


ENV_FILE = Path(os.environ.get("YASINRELAY_ENV_FILE", ".env"))


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
    schedule_interval: int = 1800
    ai_provider: str = "yasinai"
    event_bus_enabled: bool = True
    event_logging_enabled: bool = True


def _prompt_value(label: str, current: str, *, secret: bool = False, required: bool = False) -> str:
    """Prompt for a value; an empty answer keeps the current value."""
    shown = "********" if secret and current else current
    suffix = f" [{shown}]" if shown else ""
    while True:
        try:
            value = getpass.getpass(f"{label}{suffix}: ") if secret else input(f"{label}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            value = ""
        if value:
            return value
        if current:
            return current
        if not required:
            return ""
        print("این مقدار الزامی است؛ لطفاً مقدار را وارد کنید.")


def _set_env_value(key: str, value: str) -> None:
    if value:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)


def _write_env(values: dict[str, str]) -> None:
    """Update known keys in .env while preserving unrelated user settings."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    remaining = dict(values)
    output: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key not in remaining:
            output.append(line)
            continue
        value = remaining.pop(key)
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        output.append(f'{key}="{escaped}"')

    if output and output[-1].strip():
        output.append("")
    for key, value in remaining.items():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        output.append(f'{key}="{escaped}"')

    ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass


def configure_interactively() -> None:
    """Collect runtime settings and persist them to the local .env file."""
    print("\n===== YasinRelay Configuration =====")
    print("برای نگه‌داشتن مقدار قبلی فقط Enter بزنید.\n")

    values = {
        "EITAA_TOKEN": _prompt_value("توکن ایتایار", os.environ.get("EITAA_TOKEN", ""), secret=True, required=True),
        "EITAA_CHANNEL": _prompt_value("کانال مقصد ایتا", os.environ.get("EITAA_CHANNEL", ""), required=True),
        "SOURCE_CHANNELS": _prompt_value(
            "کانال‌های منبع تلگرام (با کاما جدا کنید)", os.environ.get("SOURCE_CHANNELS", ""), required=True
        ),
        "AI_PROVIDER": _prompt_value("AI Provider", os.environ.get("AI_PROVIDER", "yasinai")),
        "AI_API_KEY": _prompt_value(
            "کلید API هوش مصنوعی (اختیاری)",
            os.environ.get("AI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
            secret=True,
        ),
        "AI_MODEL": _prompt_value("مدل AI", os.environ.get("AI_MODEL", "gpt-4o-mini")),
        "AI_BASE_URL": _prompt_value("AI Base URL", os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")),
        "FETCH_INTERVAL_SECONDS": _prompt_value("فاصله اجرای بعدی (ثانیه)", os.environ.get("FETCH_INTERVAL_SECONDS", "3600")),
        "INTER_MESSAGE_DELAY_SECONDS": _prompt_value("فاصله بین ارسال پیام‌ها (ثانیه)", os.environ.get("INTER_MESSAGE_DELAY_SECONDS", "15")),
        "DATABASE_PATH": _prompt_value("مسیر دیتابیس", os.environ.get("DATABASE_PATH", "relay.db")),
        "LOG_LEVEL": _prompt_value("سطح لاگ", os.environ.get("LOG_LEVEL", "INFO")),
        "EVENT_BUS_ENABLED": _prompt_value("Event Bus", os.environ.get("EVENT_BUS_ENABLED", "true")),
        "EVENT_LOGGING_ENABLED": _prompt_value("Event Logging", os.environ.get("EVENT_LOGGING_ENABLED", "true")),
    }

    for key, value in values.items():
        _set_env_value(key, value)
    _write_env(values)
    print(f"\nتنظیمات ذخیره شد: {ENV_FILE}\n")


def load_config() -> RelayConfig:
    token = os.environ.get("EITAA_TOKEN", "")
    channel = os.environ.get("EITAA_CHANNEL", "")
    sources_raw = os.environ.get("SOURCE_CHANNELS", "")
    sources = [s.strip() for s in sources_raw.split(",") if s.strip()]

    database_path = os.environ.get("DATABASE_PATH", "relay.db")
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    fetch_interval = int(os.environ.get("FETCH_INTERVAL_SECONDS", "3600"))
    schedule_interval_raw = os.environ.get("SCHEDULE_INTERVAL")
    schedule_interval = int(schedule_interval_raw) if schedule_interval_raw is not None else fetch_interval
    ai_provider = os.environ.get("AI_PROVIDER", "yasinai")
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
