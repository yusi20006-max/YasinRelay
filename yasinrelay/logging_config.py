"""
logging_config.py
پیکربندی سیستم لاگینگ پایتون برای پروژه YasinRelay.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


class SensitiveMaskingFormatter(logging.Formatter):
    """فرمت‌کننده سفارشی لاگ برای سانسور و حذف توکن‌ها و کلیدهای امنیتی حساس."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)

        # دریافت کلیدهای حساس از محیط جهت فیلتر کردن هوشمند
        eitaa_token = os.environ.get("EITAA_TOKEN", "")
        ai_api_key = os.environ.get("AI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

        if eitaa_token and len(eitaa_token) > 3:
            formatted = formatted.replace(eitaa_token, "[EITAA_TOKEN_REDACTED]")

        if ai_api_key and len(ai_api_key) > 3:
            formatted = formatted.replace(ai_api_key, "[AI_API_KEY_REDACTED]")

        return formatted


def setup_logging(log_level: str = "INFO") -> None:
    # ساختن پوشه لاگ‌ها در صورت عدم وجود
    os.makedirs("logs", exist_ok=True)

    # تبدیل رشته لاگ‌لول به فرمت عددی logging پایتون
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # پاک کردن هندلرهای قبلی برای جلوگیری از تکرار لاگ‌ها
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # فرمت لاگ‌ها به همراه قابلیت سانسور اطلاعات حساس
    formatter = SensitiveMaskingFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # هندلر خروجی کنسول (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)

    # هندلر فایل لاگ عمومی (relay.log)
    relay_handler = RotatingFileHandler(
        "logs/relay.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    relay_handler.setFormatter(formatter)
    relay_handler.setLevel(numeric_level)
    root_logger.addHandler(relay_handler)

    # هندلر فایل لاگ خطاها (error.log)
    error_handler = RotatingFileHandler(
        "logs/error.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
