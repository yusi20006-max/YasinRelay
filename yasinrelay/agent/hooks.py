"""
hooks.py
سیستم ثبت و اجرای لایف‌سایکل هوکس (Lifecycle Hooks) در پلتفرم ایجنت.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)


class LifecycleHooks:
    """مدیریت هوک‌های مختلف در فرآیند اجرای تسک‌ها و ایجنت‌ها."""

    def __init__(self) -> None:
        self._hooks: Dict[str, List[Callable[..., Any]]] = {
            "before_plan": [],
            "after_plan": [],
            "before_execute": [],
            "after_execute": [],
            "before_tool": [],
            "after_tool": [],
            "on_retry": [],
            "on_error": [],
            "on_success": [],
            "on_finish": [],
        }

    def register(self, hook_name: str, callback: Callable[..., Any]) -> None:
        """ثبت هوک برای یکی از مراحل چرخه حیات ایجنت."""
        if hook_name in self._hooks:
            self._hooks[hook_name].append(callback)
            logger.debug(f"هوک {hook_name} جدید با موفقیت ثبت شد.")
        else:
            raise ValueError(f"هوک ناشناخته: {hook_name}")

    def trigger(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """اجرای تمام هوک‌های ثبت‌شده برای یک مرحله خاص."""
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"خطا در اجرای هوک '{hook_name}': {e}",
                        exc_info=True,
                    )
