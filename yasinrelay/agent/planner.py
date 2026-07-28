"""
planner.py
رابط‌های طراح برنامه (Planner Interface) و پیاده‌سازی‌های الگو محور و شبیه‌سازی LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BasePlanner(ABC):
    """رابط پایه‌ی سیستم‌های برنامه‌ریزی (Planner)."""

    @abstractmethod
    def create_plan(self, task_description: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ایجاد لیستی از گام‌های برنامه‌ریزی‌شده بر اساس توضیحات تسک و زمینه جاری."""
        pass


class TemplatePlanner(BasePlanner):
    """برنامه‌ریز ساده‌ی مبتنی بر قالب‌های از پیش‌تعریف‌شده (Rule/Template Based)."""

    def __init__(self, templates: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> None:
        self.templates = templates or {
            "default": [
                {"step": 1, "action": "fetch", "description": "دریافت محتوا از کانال‌های تلگرام منبع"},
                {"step": 2, "action": "process", "description": "پردازش محتوای دریافت‌شده با هوش مصنوعی"},
                {"step": 3, "action": "publish", "description": "انتشار خودکار محتوای نهایی در پیام‌رسان ایتا"},
            ]
        }

    def create_plan(self, task_description: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        # تلاش برای تطبیق متن تسک با قالب‌ها
        task_lower = task_description.lower()
        for key, plan in self.templates.items():
            if key in task_lower:
                return plan
        return self.templates["default"]


class StubLLMPlanner(BasePlanner):
    """یک پیاده‌سازی شبیه‌سازی‌شده (Stub) از طراح مبتنی بر مدل زبانی بزرگ (LLM) برای کارهای پویا در آینده."""

    def create_plan(self, task_description: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        # شبیه‌سازی رفتار یک مدل هوشمند در طراحی تسک اختصاصی
        return [
            {
                "step": 1,
                "action": "llm_analysis",
                "description": f"تحلیل عمیق هدف کاربر با استفاده از هوش مصنوعی: {task_description}",
            },
            {
                "step": 2,
                "action": "execute_with_tools",
                "description": "فراخوانی ابزارها و پلاگین‌های شناسایی‌شده بر اساس کانتکست",
            },
            {
                "step": 3,
                "action": "verify_result",
                "description": "تایید صحت خروجی و ثبت تاریخچه اجرای نهایی در پایگاه‌داده",
            },
        ]
