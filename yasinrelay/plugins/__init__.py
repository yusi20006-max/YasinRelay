"""
yasinrelay.plugins
ماژول اصلی پلتفرم پلاگین‌ها برای مدیریت، تعریف و لود داینامیک افزونه‌ها در YasinRelay.
"""

from .base import BasePlugin, SourcePlugin, AIPlugin, MediaPlugin, PublisherPlugin
from .manager import PluginManager

__all__ = [
    "BasePlugin",
    "SourcePlugin",
    "AIPlugin",
    "MediaPlugin",
    "PublisherPlugin",
    "PluginManager",
]
