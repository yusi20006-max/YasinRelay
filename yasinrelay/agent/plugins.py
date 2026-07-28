"""
plugins.py
سیستم بارگذاری و کشف خودکار پلاگین‌ها (Plugin Discovery) با امنیت ایزوله‌سازی بالا.
"""

from __future__ import annotations

import os
import sys
import importlib.util
import logging
from typing import Any, Dict, Callable

logger = logging.getLogger(__name__)


class PluginRegistry:
    """ثبت‌کننده مرکزی برای نگه‌داری و فراخوانی پلاگین‌های بارگذاری‌شده."""

    def __init__(self) -> None:
        self.plugins: Dict[str, Any] = {}

    def register(self, name: str, plugin_instance: Any) -> None:
        """ثبت یک نمونه یا کلاس پلاگین با نام منحصر‌به‌فرد."""
        self.plugins[name] = plugin_instance
        logger.info(f"پلاگین با نام '{name}' با موفقیت ثبت شد.")

    def get_plugin(self, name: str) -> Any:
        """بازیابی پلاگین از روی نام."""
        return self.plugins.get(name)

    def list_plugins(self) -> Dict[str, Any]:
        """لیست تمامی پلاگین‌های ثبت‌شده."""
        return self.plugins


# رجیستری سراسری
registry = PluginRegistry()


def register_plugin(name: str) -> Callable[[Any], Any]:
    """دکوراتور برای ثبت سریع‌تر پلاگین‌ها."""
    def decorator(cls_or_func: Any) -> Any:
        registry.register(name, cls_or_func)
        return cls_or_func
    return decorator


def discover_plugins(plugins_dir: str = "plugins") -> None:
    """
    کشف و بارگذاری خودکار تمام پلاگین‌ها از پوشه مشخص‌شده به صورت ایزوله.
    خطاهای احتمالی در حین بارگذاری هر پلاگین، فرآیند را قطع نخواهند کرد.
    """
    if not os.path.exists(plugins_dir):
        try:
            os.makedirs(plugins_dir, exist_ok=True)
            logger.info(f"پوشه پلاگین‌ها وجود نداشت؛ پوشه جدید {plugins_dir} ایجاد شد.")
        except Exception as e:
            logger.error(f"امکان ایجاد پوشه پلاگین‌ها وجود ندارد: {e}")
            return

    # افزودن پوشه پلاگین‌ها به sys.path برای شناسایی بهتر ماژول‌ها توسط مفسر
    if plugins_dir not in sys.path:
        sys.path.insert(0, plugins_dir)

    for item in os.listdir(plugins_dir):
        item_path = os.path.join(plugins_dir, item)
        module_name = None

        # بررسی فایل‌های پایتون تک‌سورس یا پکیج‌های دارای __init__.py
        if os.path.isfile(item_path) and item.endswith(".py") and not item.startswith("_"):
            module_name = item[:-3]
        elif os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
            module_name = item

        if module_name:
            try:
                # بارگذاری ایزوله با کمک importlib
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    os.path.join(plugins_dir, item if os.path.isfile(item_path) else f"{item}/__init__.py")
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # تضمین ثبت در sys.modules برای فرآیندهای ایمپورت داخلی
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    logger.info(f"پلاگین با موفقیت بارگذاری شد: {module_name}")
            except Exception as e:
                # خرابی در بارگذاری یک پلاگین، نباید کل برنامه را متوقف کند
                logger.error(
                    f"بارگذاری پلاگین {module_name} از مسیر {item_path} با خطا مواجه شد: {e}",
                    exc_info=True,
                )
