"""
test_plugin_system.py
تست‌های جامع برای معماری پلاگین‌ها و سیستم گسترش‌پذیری (Plugin Architecture) در YasinRelay.
"""

import os
import tempfile
from unittest.mock import Mock, patch
import pytest

from yasinrelay.event_bus import EventBus, PipelineEvent, EVENT_PROCESSING_FAILED, EVENT_CONTENT_RECEIVED
from yasinrelay.integration import integration_registry
from yasinrelay.plugins.base import BasePlugin, SourcePlugin, AIPlugin, MediaPlugin, PublisherPlugin
from yasinrelay.plugins.manager import PluginManager
from yasinrelay.fetch_engine import Post
from yasinrelay.ai_processor import ProcessedContent


# ---------------------------------------------------------------------------
# تست‌های اینترفیس‌ها و ساختار پایه پلاگین‌ها
# ---------------------------------------------------------------------------

def test_base_plugin_instantiation():
    """بررسی عدم امکان نمونه‌سازی مستقیم از BasePlugin به دلیل انتزاعی بودن."""
    with pytest.raises(TypeError):
        BasePlugin()


def test_custom_plugin_properties():
    """بررسی مقداردهی اولیه‌‌ی ویژگی‌های پیش‌فرض در پلاگین سفارشی."""
    class SimplePlugin(BasePlugin):
        @property
        def plugin_id(self) -> str:
            return "simple_test"

        @property
        def name(self) -> str:
            return "Simple Test Plugin"

    plugin = SimplePlugin(settings={"key": "value"})
    assert plugin.plugin_id == "simple_test"
    assert plugin.name == "Simple Test Plugin"
    assert plugin.version == "1.0.0"
    assert plugin.enabled is True
    assert plugin.settings == {"key": "value"}


# ---------------------------------------------------------------------------
# تست‌های PluginManager (کشف، لود، مدیریت چرخه حیات و ایزوله‌سازی خطاها)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_plugin_dir():
    """ایجاد یک دایرکتوری موقت برای نوشتن فیزیکی فایل‌های پلاگین تستی."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_plugin_discovery_and_loading(temp_plugin_dir):
    """بررسی فرآیند کشف خودکار و بارگذاری موفق پلاگین فیزیکی از دایرکتوری موقت."""
    # نوشتن کد یک AIPlugin تستی در دایرکتوری موقت
    plugin_code = """
from yasinrelay.plugins.base import AIPlugin
from yasinrelay.fetch_engine import Post
from yasinrelay.ai_processor import ProcessedContent

class DummyAIPlugin(AIPlugin):
    @property
    def plugin_id(self) -> str:
        return "dummy_ai"

    @property
    def name(self) -> str:
        return "Dummy AI Processor"

    def process(self, post: Post) -> ProcessedContent:
        return ProcessedContent(source_post=post, text=f"[Dummy] {post.text}")
"""
    plugin_file = os.path.join(temp_plugin_dir, "dummy_ai_plugin.py")
    with open(plugin_file, "w", encoding="utf-8") as f:
        f.write(plugin_code)

    bus = EventBus(enabled=True, logging_enabled=False)
    manager = PluginManager(
        plugin_paths=[temp_plugin_dir],
        enabled_plugins=["dummy_ai"],
        event_bus=bus,
    )

    # تست کشف پلاگین‌ها
    discovered = manager.discover_plugins()
    assert "dummy_ai" in discovered
    assert discovered["dummy_ai"].__name__ == "DummyAIPlugin"

    # تست لود و راه‌اندازی اولیه پلاگین
    loaded = manager.load_and_initialize_plugins()
    assert "dummy_ai" in loaded
    plugin_instance = loaded["dummy_ai"]
    assert plugin_instance.enabled is True

    # بررسی ثبت خودکار در integration_registry
    assert integration_registry.get_plugin("dummy_ai") == plugin_instance
    assert integration_registry.get_ai_provider("dummy_ai") == plugin_instance.__class__

    # اجرای متد پردازش پلاگین و تایید کارکرد آن
    post = Post(channel="@test", message_id="1", text="سلام")
    res = plugin_instance.process(post)
    assert res.text == "[Dummy] سلام"


def test_plugin_enable_disable_lifecycle(temp_plugin_dir):
    """بررسی امکان فعال/غیرفعال کردن پویا (enable/disable) پلاگین و صدا زدن متدهای چرخه حیات."""
    plugin_code = """
from yasinrelay.plugins.base import BasePlugin

class LifecyclePlugin(BasePlugin):
    def __init__(self, settings=None):
        super().__init__(settings)
        self.init_called = False
        self.shutdown_called = False

    @property
    def plugin_id(self) -> str:
        return "lifecycle_test"

    @property
    def name(self) -> str:
        return "Lifecycle Test"

    def initialize(self, event_bus, registry):
        self.init_called = True

    def shutdown(self):
        self.shutdown_called = True
"""
    plugin_file = os.path.join(temp_plugin_dir, "lifecycle_plugin.py")
    with open(plugin_file, "w", encoding="utf-8") as f:
        f.write(plugin_code)

    bus = EventBus(enabled=True, logging_enabled=False)
    manager = PluginManager(
        plugin_paths=[temp_plugin_dir],
        enabled_plugins=["lifecycle_test"],
        event_bus=bus,
    )

    manager.load_and_initialize_plugins()
    plugin = manager.get_plugin("lifecycle_test")
    assert plugin is not None
    assert plugin.init_called is True
    assert plugin.shutdown_called is False

    # غیرفعال کردن پلاگین
    assert manager.disable_plugin("lifecycle_test") is True
    assert plugin.shutdown_called is True
    assert plugin.enabled is False
    assert manager.get_plugin("lifecycle_test") is None

    # فعال‌سازی مجدد پلاگین
    assert manager.enable_plugin("lifecycle_test") is True
    new_plugin = manager.get_plugin("lifecycle_test")
    assert new_plugin is not None
    assert new_plugin.enabled is True


def test_plugin_event_communication(temp_plugin_dir):
    """بررسی قابلیت عضویت در رویدادها، واکنش به رویدادهای پایپ‌لاین و انتشار رویداد از داخل پلاگین."""
    plugin_code = """
from yasinrelay.plugins.base import BasePlugin
from yasinrelay.event_bus import PipelineEvent

class EventTestPlugin(BasePlugin):
    def __init__(self, settings=None):
        super().__init__(settings)
        self.last_received_content_id = None

    @property
    def plugin_id(self) -> str:
        return "event_test"

    @property
    def name(self) -> str:
        return "Event Test"

    def initialize(self, event_bus, registry):
        event_bus.subscribe("ContentReceived", self.on_content)

    def on_content(self, event: PipelineEvent):
        self.last_received_content_id = event.content_id
"""
    plugin_file = os.path.join(temp_plugin_dir, "event_test_plugin.py")
    with open(plugin_file, "w", encoding="utf-8") as f:
        f.write(plugin_code)

    bus = EventBus(enabled=True, logging_enabled=False)
    manager = PluginManager(
        plugin_paths=[temp_plugin_dir],
        enabled_plugins=["event_test"],
        event_bus=bus,
    )

    manager.load_and_initialize_plugins()
    plugin = manager.get_plugin("event_test")

    # شبیه‌سازی انتشار یک رویداد در پایپ‌لاین
    bus.publish(PipelineEvent(name="ContentReceived", content_id="channel:123"))
    assert plugin.last_received_content_id == "channel:123"


def test_plugin_manager_failure_isolation_and_events(temp_plugin_dir):
    """بررسی ایزوله‌سازی خطاهای زمان کشف/لود پلاگین خراب و انتشار رویداد شکست."""
    # ۱. ایجاد یک فایل پایتون خراب با خطای سینتکسی برای تست شکست در فاز discovery
    broken_code = "class BrokenPlugin(BasePlugin: invalid syntax code"
    with open(os.path.join(temp_plugin_dir, "broken_syntax.py"), "w", encoding="utf-8") as f:
        f.write(broken_code)

    # ۲. ایجاد یک پلاگین معتبر که در initialize خطا می‌دهد برای تست شکست در فاز initialization
    broken_init_code = """
from yasinrelay.plugins.base import BasePlugin

class BrokenInitPlugin(BasePlugin):
    @property
    def plugin_id(self) -> str:
        return "broken_init"

    @property
    def name(self) -> str:
        return "Broken Init"

    def initialize(self, event_bus, registry):
        raise ValueError("خطای پیش‌فرض راه‌اندازی")
"""
    with open(os.path.join(temp_plugin_dir, "broken_init.py"), "w", encoding="utf-8") as f:
        f.write(broken_init_code)

    bus = EventBus(enabled=True, logging_enabled=False)
    emitted_failures = []

    def failure_listener(event: PipelineEvent):
        if event.name == EVENT_PROCESSING_FAILED:
            emitted_failures.append(event)

    bus.subscribe(EVENT_PROCESSING_FAILED, failure_listener)

    manager = PluginManager(
        plugin_paths=[temp_plugin_dir],
        enabled_plugins=["broken_init"],
        event_bus=bus,
    )

    # تلاش برای لود و راه‌اندازی؛ شکست فاز دیسکاوری یا اینیشیالایز نباید کل فرآیند را کرش دهد
    try:
        manager.load_and_initialize_plugins()
    except Exception as exc:
        pytest.fail(f"خطای لود پلاگین نباید منتشر شود و مانع فرآیند گردد: {exc}")

    # تایید انتشار حداقل یک رویداد شکست (پلاگین broken_init خطا داده است)
    assert len(emitted_failures) >= 1
    assert any("broken_init" in ev.payload.get("target", "") for ev in emitted_failures)
