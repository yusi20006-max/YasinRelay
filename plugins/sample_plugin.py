"""
sample_plugin.py
نمونه پلاگین ساده جهت نمایش کارکرد کشف خودکار و ثبت پلاگین‌ها در پلتفرم ایجنت.
"""

from __future__ import annotations

import logging
from yasinrelay.agent import register_plugin

logger = logging.getLogger(__name__)


@register_plugin("text_decorator")
class TextDecoratorPlugin:
    """پلاگین تزیین‌کننده متن که متن‌های خروجی را با پیشوند و پسوند متمایز می‌کند."""

    def __init__(self, prefix: str = "✨", suffix: str = "✨") -> None:
        self.prefix = prefix
        self.suffix = suffix

    def execute(self, text: str) -> str:
        logger.info("در حال تزیین متن با پلاگین text_decorator...")
        return f"{self.prefix} {text} {self.suffix}"
