"""
hub_integration.py
لایه ادغام پویا با YasinHub برای هماهنگ‌سازی وضعیت ران‌تایم.
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def report_hub_status(success: bool, message: str) -> None:
    """
    ثبت و هماهنگ‌سازی وضعیت اجرای YasinRelay با YasinHub.
    این تابع ابتدا تلاش می‌کند تا از کتابخانه yasinhub استفاده کند و در صورت عدم نصب بودن،
    به طور مستقیم در مسیر استاندارد فایل وضعیت را می‌نویسد.
    """
    logger.info(f"[YasinHub Integration] گزارش وضعیت: موفقیت={success} | پیام: {message}")

    # ۱. تلاش برای استفاده از YasinHub در صورت نصب بودن در محیط ران‌تایم
    try:
        from yasinhub.status_store import write_status
        write_status("yasinrelay", success=success, message=message)
        logger.info("[YasinHub Integration] وضعیت با موفقیت از طریق SDK عمومی YasinHub ثبت شد.")
        return
    except ImportError:
        logger.debug("[YasinHub Integration] کتابخانه yasinhub پیدا نشد؛ استفاده از ثبت مستقیم فایل JSON.")

    # ۲. نوشتن مستقیم در فایل وضعیت (Fallback به آدرس پیش‌فرض اکوسیستم)
    try:
        # دریافت دایرکتوری وضعیت‌ها از متغیرهای محیطی مشترک
        status_dir_env = os.environ.get("YASIN_STATUS_DIR") or os.environ.get("YASINHUB_STATUS_DIR")
        if status_dir_env:
            status_dir = Path(status_dir_env)
        else:
            status_dir = Path.home() / ".yasin_status"

        status_dir.mkdir(parents=True, exist_ok=True)
        path = status_dir / "yasinrelay.json"

        # دریافت اطلاعات سلامت از مانیتورینگ برای گزارش به هاب
        health_report = None
        try:
            from .monitoring import get_health_monitor
            health_report = get_health_monitor().get_health_report()
        except Exception as e:
            logger.debug(f"[YasinHub Integration] خطا در واکشی گزارش سلامت برای هاب: {e}")

        payload = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "message": message,
        }
        if health_report:
            payload["health"] = health_report

        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"[YasinHub Integration] فایل وضعیت مستقیماً در مسیر '{path}' ذخیره شد.")
    except Exception as e:
        logger.error(f"[YasinHub Integration] خطا در ذخیره‌سازی مستقیم فایل وضعیت: {e}", exc_info=True)
