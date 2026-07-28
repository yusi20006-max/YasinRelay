"""
context.py
مدیریت زمینه اجرا (Context Manager)، متغیرهای اشتراکی و تاریخچه فعالیت‌ها.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class ContextManager:
    """مدیریت کننده کانتکست و تاریخچه اجرای تسک‌ها برای هماهنگی با مدل‌های زبانی در آینده."""

    def __init__(self) -> None:
        self.shared_variables: Dict[str, Any] = {}
        self.task_metadata: Dict[str, Any] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.started_at: datetime = datetime.now()

    def set_variable(self, key: str, value: Any) -> None:
        """ذخیره یک متغیر مشترک در کانتکست."""
        self.shared_variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """بازیابی یک متغیر مشترک."""
        return self.shared_variables.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """تنظیم متادیتای مرتبط با تسک جاری."""
        self.task_metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """بازیابی متادیتای تسک جاری."""
        return self.task_metadata.get(key, default)

    def log_history_step(self, step_type: str, details: Dict[str, Any]) -> None:
        """ثبت یک گام اجرایی جدید در تاریخچه فرآیند."""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": step_type,
            "details": details,
        })

    def get_history(self) -> List[Dict[str, Any]]:
        """بازیابی کل تاریخچه اجرا."""
        return self.execution_history

    def get_llm_context(self) -> Dict[str, Any]:
        """فرمت‌دهی و آماده‌سازی تمام اطلاعات کانتکست برای استفاده مدل زبانی."""
        return {
            "metadata": self.task_metadata,
            "variables": self.shared_variables,
            "history": self.execution_history,
            "elapsed_seconds": (datetime.now() - self.started_at).total_seconds(),
        }
