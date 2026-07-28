"""
workflow.py
پایه و اساس زیرساخت اجرای جریان‌های کاری (Workflow Engine) چندتسک، موازی و شرطی.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowStep:
    """نماینده‌ی یک گام در جریان کاری با پشتیبانی از کارهای شرطی، موازی و تودرتو."""

    def __init__(
        self,
        name: str,
        action: Callable[[Dict[str, Any]], Any],
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        parallel_steps: Optional[List[WorkflowStep]] = None,
        sub_workflow: Optional[Workflow] = None,
    ) -> None:
        self.name = name
        self.action = action
        self.condition = condition
        self.parallel_steps = parallel_steps or []
        self.sub_workflow = sub_workflow

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """بررسی برقرار بودن شرط جهت اجرای گام فعلی."""
        if self.condition:
            try:
                res = self.condition(context)
                logger.debug(f"شرط گام '{self.name}' بررسی شد: {res}")
                return res
            except Exception as e:
                logger.error(f"خطا در ارزیابی شرط گام '{self.name}': {e}", exc_info=True)
                return False
        return True


class Workflow:
    """نماینده‌ی یک ورک‌فلو/جریان کاری کامل متشکل از چندین گام ترتیبی یا موازی."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.steps: List[WorkflowStep] = []

    def add_step(self, step: WorkflowStep) -> None:
        """افزودن گام به جریان کاری."""
        self.steps.append(step)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """اجرای ترتیبی و موازی گام‌های جریان کاری روی کانتکست مشترک."""
        logger.info(f"شروع اجرای جریان کاری: '{self.name}'")
        for step in self.steps:
            if not step.should_execute(context):
                logger.info(f"گام '{step.name}' به دلیل عدم ارضای شرط، نادیده گرفته شد.")
                continue

            logger.info(f"در حال اجرای گام: '{step.name}'")

            # ۱. گام‌های موازی
            if step.parallel_steps:
                logger.info(f"در حال اجرای گام‌های موازی داخل گام: '{step.name}'")
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for p_step in step.parallel_steps:
                        if p_step.should_execute(context):
                            futures.append(
                                executor.submit(p_step.action, context)
                            )
                    # منتظر ماندن برای پایان تمام تسک‌های موازی
                    results = [f.result() for f in futures]
                    context[f"{step.name}_parallel_results"] = results

            # ۲. ساب‌ورک‌فلو (ورک‌فلوهای تودرتو)
            elif step.sub_workflow:
                logger.info(f"در حال اجرای جریان کاری زیرمجموعه (Sub-workflow) برای گام: '{step.name}'")
                context[f"{step.name}_sub_workflow_result"] = step.sub_workflow.execute(context)

            # ۳. اجرای ترتیبی تک‌تسکی
            else:
                try:
                    res = step.action(context)
                    context[f"{step.name}_result"] = res
                except Exception as e:
                    logger.error(f"خطا در اجرای گام ترتیبی '{step.name}': {e}", exc_info=True)
                    raise e

        logger.info(f"پایان موفقیت‌آمیز جریان کاری: '{self.name}'")
        return context
