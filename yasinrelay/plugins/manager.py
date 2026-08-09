"""
manager.py
مدیریت چرخه حیات، کشف خودکار، اعتبارسنجی و لود پلاگین‌ها در YasinRelay.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Type

from yasinrelay.event_bus import get_event_bus, PipelineEvent, EVENT_PROCESSING_FAILED
from yasinrelay.integration import integration_registry
from .base import BasePlugin, SourcePlugin, AIPlugin, MediaPlugin, PublisherPlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """مسئول مدیریت کامل فرآیند کشف، لود، فعال/غیرفعال‌سازی و اعتبارسنجی پلاگین‌ها."""

    def __init__(
        self,
        plugin_paths: Optional[List[str]] = None,
        enabled_plugins: Optional[List[str]] = None,
        plugin_settings: Optional[Dict[str, Any]] = None,
        event_bus: Any = None,
    ) -> None:
        self.plugin_paths: List[str] = plugin_paths or ["plugins", "yasinrelay/plugins"]
        self.enabled_plugin_ids: List[str] = enabled_plugins or []
        self.plugin_settings: Dict[str, Any] = plugin_settings or {}
        self.event_bus = event_bus or get_event_bus()

        # نگهداری پلاگین‌های کشف شده و بارگذاری شده
        self._discovered_classes: Dict[str, Type[BasePlugin]] = {}
        self._loaded_plugins: Dict[str, BasePlugin] = {}

    def discover_plugins(self) -> Dict[str, Type[BasePlugin]]:
        """جستجو و کشف خودکار تمامی کلاس‌های پلاگین در مسیرهای مشخص شده."""
        logger.info(f"[PluginManager] شروع کشف خودکار پلاگین‌ها در مسیرهای: {self.plugin_paths}")
        self._discovered_classes.clear()

        for path in self.plugin_paths:
            if not os.path.isdir(path):
                logger.debug(f"[PluginManager] مسیر پلاگین وجود ندارد: {path}")
                continue

            for entry in os.listdir(path):
                if entry.startswith("_") or entry.startswith("."):
                    continue

                full_path = os.path.join(path, entry)
                if os.path.isfile(full_path) and entry.endswith(".py"):
                    module_name = entry[:-3]
                    self._load_classes_from_file(full_path, module_name)
                elif os.path.isdir(full_path):
                    init_file = os.path.join(full_path, "__init__.py")
                    if os.path.isfile(init_file):
                        self._load_classes_from_file(init_file, entry)

        logger.info(f"[PluginManager] تعداد {len(self._discovered_classes)} پلاگین کشف شد.")
        return dict(self._discovered_classes)

    def _load_classes_from_file(self, file_path: str, module_name: str) -> None:
        """بارگذاری داینامیک فایل پایتون و شناسایی کلاس‌های پلاگین درون آن."""
        try:
            spec = importlib.util.spec_from_file_location(f"yasinrelay.plugins.dynamic.{module_name}", file_path)
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module, inspect.isclass):
                # باید حتماً زیرکلاسی از BasePlugin باشد و کلاس انتزاعی یا واسط‌های اصلی نباشد
                if issubclass(obj, BasePlugin) and obj not in (BasePlugin, SourcePlugin, AIPlugin, MediaPlugin, PublisherPlugin):
                    # اعتبارسنجی سازگاری
                    if self._validate_plugin_compatibility(obj):
                        # نمونه‌سازی آزمایشی موقت برای دریافت شناسه پلاگین
                        plugin_id = obj.plugin_id if hasattr(obj, "plugin_id") and isinstance(obj.plugin_id, str) else None
                        if not plugin_id:
                            try:
                                temp_instance = obj()
                                plugin_id = temp_instance.plugin_id
                            except Exception:
                                pass

                        if plugin_id:
                            self._discovered_classes[plugin_id] = obj
                            logger.info(f"[PluginManager] پلاگین کشف شد: {plugin_id} (کلاس: {obj.__name__})")
                        else:
                            logger.warning(f"[PluginManager] کلاس پلاگین {name} فاقد plugin_id معتبر است.")
                    else:
                        logger.warning(f"[PluginManager] کلاس پلاگین {name} سازگار نیست.")
        except Exception as exc:
            logger.error(f"[PluginManager] خطا در لود ماژول {module_name} از فایل {file_path}: {exc}", exc_info=True)
            self._emit_plugin_failure_event("discovery", f"فایل: {file_path}", exc)

    def _validate_plugin_compatibility(self, plugin_class: Type[BasePlugin]) -> bool:
        """بررسی ساختار کلاس پلاگین جهت انطباق با نیازمندی‌های سیستم."""
        try:
            # بررسی وجود متدهای حیاتی و ساختار ارث‌بری
            required_attrs = ["plugin_id", "name"]
            for attr in required_attrs:
                if not hasattr(plugin_class, attr):
                    return False
            return True
        except Exception:
            return False

    def load_and_initialize_plugins(self) -> Dict[str, BasePlugin]:
        """لود، اعتبارسنجی و راه‌اندازی اولیه تمامی پلاگین‌های فعال بر اساس پیکربندی."""
        # ابتدا کشف مجدد
        self.discover_plugins()

        for plugin_id, plugin_class in self._discovered_classes.items():
            # بررسی فعال بودن (اگر لیست enabled خالی نباشد، باید در آن حضور داشته باشد)
            # اگر لیست کلاً خالی باشد، به صورت پیش‌فرض فعال در نظر می‌گیریم یا برعکس بر اساس منطق پروداکشن
            # در سیستم YasinRelay، اگر لیست فعال مشخص شده باشد، فقط آن‌ها؛ در غیر این صورت لود نمی‌شوند.
            if self.enabled_plugin_ids and plugin_id not in self.enabled_plugin_ids:
                logger.info(f"[PluginManager] پلاگین {plugin_id} در لیست فعال‌ها نیست؛ رد شد.")
                continue

            self._load_and_init_single_plugin(plugin_id, plugin_class)

        return dict(self._loaded_plugins)

    def _load_and_init_single_plugin(self, plugin_id: str, plugin_class: Type[BasePlugin]) -> Optional[BasePlugin]:
        """ساخت نمونه، مقداردهی تنظیمات و صدا زدن initialize برای یک پلاگین خاص."""
        if plugin_id in self._loaded_plugins:
            return self._loaded_plugins[plugin_id]

        logger.info(f"[PluginManager] در حال فعال‌سازی و راه‌اندازی پلاگین: {plugin_id}")
        try:
            settings = self.plugin_settings.get(plugin_id, {})
            plugin_instance = plugin_class(settings=settings)

            # ثبت در رجیستری مرکزی یکپارچه‌سازی متناسب با نوع اینترفیس پلاگین
            self._register_in_integration_registry(plugin_id, plugin_instance)

            # راه‌اندازی با فرستادن event_bus و رجیستری مرکزی برای اتصال شنونده‌ها
            plugin_instance.initialize(self.event_bus, integration_registry)
            plugin_instance.enabled = True

            self._loaded_plugins[plugin_id] = plugin_instance
            logger.info(f"[PluginManager] پلاگین {plugin_id} با موفقیت راه‌اندازی و فعال شد.")
            return plugin_instance
        except Exception as exc:
            logger.error(f"[PluginManager] خطا در راه‌اندازی اولیه پلاگین {plugin_id}: {exc}", exc_info=True)
            self._emit_plugin_failure_event("initialization", plugin_id, exc)
            return None

    def _register_in_integration_registry(self, plugin_id: str, plugin_instance: BasePlugin) -> None:
        """بررسی اینترفیس‌های پلاگین و ثبت آن در دسته‌بندی مناسب رجیستری یکپارچه‌سازی."""
        integration_registry.register_plugin(plugin_id, plugin_instance)

        if isinstance(plugin_instance, SourcePlugin):
            integration_registry.register_feed_source(plugin_id, plugin_instance.__class__)
        elif isinstance(plugin_instance, AIPlugin):
            integration_registry.register_ai_provider(plugin_id, plugin_instance.__class__)
        elif isinstance(plugin_instance, MediaPlugin):
            integration_registry.register_media_processor(plugin_id, plugin_instance.__class__)
        elif isinstance(plugin_instance, PublisherPlugin):
            integration_registry.register_publisher(plugin_id, plugin_instance.__class__)

    def enable_plugin(self, plugin_id: str) -> bool:
        """فعال‌سازی مجدد یا بارگذاری پویا و ثبت پلاگین غیرفعال."""
        if plugin_id in self._loaded_plugins:
            self._loaded_plugins[plugin_id].enabled = True
            logger.info(f"[PluginManager] پلاگین {plugin_id} مجدداً فعال شد.")
            return True

        if plugin_id in self._discovered_classes:
            plugin_class = self._discovered_classes[plugin_id]
            instance = self._load_and_init_single_plugin(plugin_id, plugin_class)
            return instance is not None

        logger.warning(f"[PluginManager] امکان فعال‌سازی وجود ندارد؛ پلاگین {plugin_id} کشف نشده است.")
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """غیرفعال‌سازی موقت، لغو شنونده‌ها و فراخوانی متد shutdown پلاگین."""
        if plugin_id in self._loaded_plugins:
            plugin = self._loaded_plugins[plugin_id]
            try:
                plugin.shutdown()
            except Exception as exc:
                logger.error(f"[PluginManager] خطا در حین توقف پلاگین {plugin_id}: {exc}", exc_info=True)
                self._emit_plugin_failure_event("shutdown", plugin_id, exc)

            plugin.enabled = False
            # حذف فیزیکی از لودشده‌ها برای خروج کامل از جریان پردازش
            self._loaded_plugins.pop(plugin_id)
            logger.info(f"[PluginManager] پلاگین {plugin_id} با موفقیت غیرفعال و خاموش شد.")
            return True

        logger.warning(f"[PluginManager] پلاگین {plugin_id} فعال نیست.")
        return False

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """دریافت نمونه پلاگین فعال بارگذاری شده."""
        return self._loaded_plugins.get(plugin_id)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """لیست کردن تمامی پلاگین‌های کشف شده و وضعیت فعال بودن آن‌ها."""
        results = []
        for plugin_id, cls in self._discovered_classes.items():
            loaded_instance = self._loaded_plugins.get(plugin_id)
            results.append({
                "plugin_id": plugin_id,
                "name": getattr(cls, "name", property(lambda self: "نامشخص")).__get__(None, cls) if hasattr(cls, "name") else "نامشخص",
                "version": getattr(cls, "version", "1.0.0"),
                "discovered": True,
                "loaded": loaded_instance is not None,
                "enabled": loaded_instance.enabled if loaded_instance else False,
            })
        return results

    def _emit_plugin_failure_event(self, stage: str, target: str, exception: Exception) -> None:
        """انتشار رویداد شکست پلاگین جهت آگاهی سایر بخش‌های ناظر سیستم رویدادها."""
        if self.event_bus:
            try:
                self.event_bus.publish(
                    PipelineEvent(
                        name=EVENT_PROCESSING_FAILED,
                        content_id=f"plugin:{target}",
                        payload={
                            "error": str(exception),
                            "stage": f"plugin_{stage}",
                            "target": target,
                        },
                        metadata={"type": "plugin_error"}
                    )
                )
            except Exception as exc:
                logger.error(f"[PluginManager] خطا در انتشار رویداد شکست پلاگین: {exc}", exc_info=True)
