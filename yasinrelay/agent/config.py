"""
config.py
سیستم تنظیمات مرکزی پلتفرم ایجنت.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AgentConfig:
    """تنظیمات مرکزی پلتفرم ایجنت با پشتیبانی از مقادیر پیش‌فرض، متغیرهای محیطی و فایل کانفیگ اختیاری."""

    def __init__(self, config_file: Optional[str] = None) -> None:
        # مقادیر پیش‌فرض
        self.retry_count: int = 3
        self.retry_delay: float = 1.0
        self.tool_timeout: float = 30.0
        self.planner_timeout: float = 60.0
        self.max_parallel_tools: int = 4
        self.log_level: str = "INFO"

        # بارگذاری از متغیرهای محیطی
        self._load_from_env()

        # بارگذاری از فایل کانفیگ در صورت وجود
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)

    def _load_from_env(self) -> None:
        self.retry_count = int(os.environ.get("AGENT_RETRY_COUNT", str(self.retry_count)))
        self.retry_delay = float(os.environ.get("AGENT_RETRY_DELAY", str(self.retry_delay)))
        self.tool_timeout = float(os.environ.get("AGENT_TOOL_TIMEOUT", str(self.tool_timeout)))
        self.planner_timeout = float(os.environ.get("AGENT_PLANNER_TIMEOUT", str(self.planner_timeout)))
        self.max_parallel_tools = int(os.environ.get("AGENT_MAX_PARALLEL_TOOLS", str(self.max_parallel_tools)))
        self.log_level = os.environ.get("AGENT_LOG_LEVEL", self.log_level)

    def _load_from_file(self, config_file: str) -> None:
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.retry_count = int(data.get("retry_count", self.retry_count))
                self.retry_delay = float(data.get("retry_delay", self.retry_delay))
                self.tool_timeout = float(data.get("tool_timeout", self.tool_timeout))
                self.planner_timeout = float(data.get("planner_timeout", self.planner_timeout))
                self.max_parallel_tools = int(data.get("max_parallel_tools", self.max_parallel_tools))
                self.log_level = data.get("log_level", self.log_level)
            logger.info(f"تنظیمات ایجنت با موفقیت از فایل {config_file} بارگذاری شد.")
        except Exception as e:
            logger.error(f"خطا در بارگذاری فایل تنظیمات ایجنت {config_file}: {e}", exc_info=True)

    def to_dict(self) -> Dict[str, Any]:
        """تبدیل تنظیمات به دیکشنری."""
        return {
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "tool_timeout": self.tool_timeout,
            "planner_timeout": self.planner_timeout,
            "max_parallel_tools": self.max_parallel_tools,
            "log_level": self.log_level,
        }
