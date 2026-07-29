"""
test_event_bus.py
تست‌های جامع برای سیستم رویدادهای داخلی (Event Bus) و لایه یکپارچه‌سازی (Integration Layer) در YasinRelay.
"""

from datetime import datetime
from unittest.mock import Mock, patch
import pytest

from yasinrelay.event_bus import (
    EventBus,
    PipelineEvent,
    get_event_bus,
    EVENT_CONTENT_RECEIVED,
    EVENT_CONTENT_NORMALIZED,
    EVENT_DUPLICATE_DETECTED,
    EVENT_PROCESSING_STARTED,
    EVENT_AI_PROCESSING_COMPLETED,
    EVENT_MEDIA_PROCESSING_COMPLETED,
    EVENT_PUBLISHING_STARTED,
    EVENT_PUBLISHING_COMPLETED,
    EVENT_PROCESSING_FAILED,
)
from yasinrelay.integration import IntegrationPlugin, IntegrationRegistry, integration_registry
from yasinrelay.pipeline_engine import (
    CollectorStage,
    NormalizerStage,
    ValidatorStage,
    DuplicateDetectionStage,
    AIProcessorStage,
    MediaProcessorStage,
    PublisherStage,
    PipelineContext,
    PipelineManager,
)
from yasinrelay.fetch_engine import FakeFetcher, Post
from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.media_processor import PassthroughMediaProcessor
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig
from yasinrelay.storage.database import Database


# ---------------------------------------------------------------------------
# تست‌های پایه Event Bus (اشتراک و انتشار)
# ---------------------------------------------------------------------------

def test_event_creation_and_to_dict():
    """بررسی صحت نمونه‌سازی کلاس PipelineEvent و خروجی دیکشنری آن."""
    now = datetime.now()
    event = PipelineEvent(
        name=EVENT_CONTENT_RECEIVED,
        content_id="test_channel:123",
        payload={"text": "hello"},
        metadata={"source": "telegram"},
        timestamp=now,
    )
    assert event.name == EVENT_CONTENT_RECEIVED
    assert event.content_id == "test_channel:123"
    assert event.payload == {"text": "hello"}
    assert event.metadata == {"source": "telegram"}
    assert event.timestamp == now

    d = event.to_dict()
    assert d["name"] == EVENT_CONTENT_RECEIVED
    assert d["content_id"] == "test_channel:123"
    assert d["payload"] == {"text": "hello"}
    assert d["metadata"] == {"source": "telegram"}
    assert d["timestamp"] == now.isoformat()


def test_event_bus_basic_pub_sub():
    """بررسی عضویت و دریافت رویداد ساده در EventBus."""
    bus = EventBus(enabled=True, logging_enabled=False)
    received_events = []

    def handle_received(event: PipelineEvent):
        received_events.append(event)

    bus.subscribe(EVENT_CONTENT_RECEIVED, handle_received)

    event = PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="chan:1")
    bus.publish(event)

    assert len(received_events) == 1
    assert received_events[0].content_id == "chan:1"


def test_event_bus_wildcard_subscription():
    """بررسی کارکرد اشتراک سراسری (*) در EventBus."""
    bus = EventBus(enabled=True, logging_enabled=False)
    received_events = []

    def handle_all(event: PipelineEvent):
        received_events.append(event)

    bus.subscribe("*", handle_all)

    bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="chan:1"))
    bus.publish(PipelineEvent(name=EVENT_CONTENT_NORMALIZED, content_id="chan:2"))

    assert len(received_events) == 2
    assert received_events[0].name == EVENT_CONTENT_RECEIVED
    assert received_events[1].name == EVENT_CONTENT_NORMALIZED


def test_event_bus_unsubscribe_and_clear():
    """بررسی کارکرد حذف عضویت (unsubscribe) و پاک‌سازی کلی (clear)."""
    bus = EventBus(enabled=True, logging_enabled=False)
    received_events = []

    def handler(event: PipelineEvent):
        received_events.append(event)

    bus.subscribe(EVENT_CONTENT_RECEIVED, handler)
    bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="1"))
    assert len(received_events) == 1

    bus.unsubscribe(EVENT_CONTENT_RECEIVED, handler)
    bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="2"))
    assert len(received_events) == 1  # نباید افزایش یابد

    # تست clear
    bus.subscribe(EVENT_CONTENT_RECEIVED, handler)
    bus.subscribe("*", handler)
    bus.clear()
    bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="3"))
    assert len(received_events) == 1  # نباید افزایش یابد


def test_event_bus_disabled():
    """بررسی کارکرد زمانی که EventBus غیرفعال است."""
    bus = EventBus(enabled=False, logging_enabled=False)
    received_events = []

    def handler(event: PipelineEvent):
        received_events.append(event)

    bus.subscribe(EVENT_CONTENT_RECEIVED, handler)
    bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="1"))
    assert len(received_events) == 0  # نباید چیزی منتشر شود


def test_handler_failure_isolation():
    """بررسی ایزوله‌سازی خطای هندلرها (خطای یک هندلر نباید مانع بقیه یا کرش شود)."""
    bus = EventBus(enabled=True, logging_enabled=False)
    calls = []

    def broken_handler(event: PipelineEvent):
        raise RuntimeError("خطای تستی در شنونده")

    def safe_handler(event: PipelineEvent):
        calls.append(event)

    bus.subscribe(EVENT_CONTENT_RECEIVED, broken_handler)
    bus.subscribe(EVENT_CONTENT_RECEIVED, safe_handler)

    # نباید استثنا بالا بیاید و safe_handler باید اجرا شود
    try:
        bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="1"))
    except Exception as exc:
        pytest.fail(f"EventBus نباید استثنا پرتاب کند: {exc}")

    assert len(calls) == 1
    assert calls[0].content_id == "1"


# ---------------------------------------------------------------------------
# تست‌های Pipeline Integration (انتشار رویدادها در مراحل پایپ‌لاین)
# ---------------------------------------------------------------------------

def test_pipeline_stages_event_emission():
    """بررسی انتشار تمامی رویدادهای مشخص‌شده توسط استیج‌های پایپ‌لاین."""
    bus = EventBus(enabled=True, logging_enabled=False)
    emitted_events = []

    def event_listener(event: PipelineEvent):
        emitted_events.append(event)

    bus.subscribe("*", event_listener)

    # آماده‌سازی دیتا و دیتابیس در حافظه موقت
    db = Database(":memory:")
    fetcher = FakeFetcher()
    post = Post(channel="@my_channel", message_id="999", text="  محتوای خام تستی با فاصله  ", media_url="http://img.jpg")
    fetcher.add_posts("@my_channel", [post])

    # 1. Collector Stage -> ContentReceived
    collector = CollectorStage(fetcher, event_bus=bus)
    contexts = collector.collect("@my_channel", limit=1)
    assert len(contexts) == 1
    assert any(ev.name == EVENT_CONTENT_RECEIVED for ev in emitted_events)

    context = contexts[0]

    # تعریف بقیه استیج‌ها به همراه گذرگاه رویدادها
    stages = [
        NormalizerStage(event_bus=bus),
        ValidatorStage(event_bus=bus),
        DuplicateDetectionStage(db, event_bus=bus),
        AIProcessorStage(PassthroughProcessor(), event_bus=bus),
        MediaProcessorStage(PassthroughMediaProcessor(), event_bus=bus),
    ]

    manager = PipelineManager(stages, event_bus=bus)
    result_ctx = manager.execute(context)

    # بررسی انتشار رویدادهای مراحل پردازش
    event_names = [ev.name for ev in emitted_events]
    assert EVENT_PROCESSING_STARTED in event_names
    assert EVENT_CONTENT_NORMALIZED in event_names
    assert EVENT_AI_PROCESSING_COMPLETED in event_names
    assert EVENT_MEDIA_PROCESSING_COMPLETED in event_names

    # انتشار نهایی (PublisherStage) با موک کردن درخواست
    with patch("yasinrelay.eitaa_publisher.requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=200, text="ok")
        publisher_stage = PublisherStage(EitaaPublisher(EitaaConfig("TOKEN", "@chan")), db, event_bus=bus)
        publisher_stage.process(result_ctx)

    event_names = [ev.name for ev in emitted_events]
    assert EVENT_PUBLISHING_STARTED in event_names
    assert EVENT_PUBLISHING_COMPLETED in event_names
    db.close()


def test_pipeline_manager_processing_failed_event():
    """بررسی انتشار رویداد ProcessingFailed در زمان بروز خطا یا استثنا در استیج."""
    bus = EventBus(enabled=True, logging_enabled=False)
    emitted_events = []

    def event_listener(event: PipelineEvent):
        emitted_events.append(event)

    bus.subscribe("*", event_listener)

    class BrokenStageInTest(NormalizerStage):
        def process(self, context: PipelineContext) -> PipelineContext:
            raise ValueError("یک خطای فرضی")

    post = Post(channel="@test", message_id="10", text="محتوا")
    context = PipelineContext(post=post)

    manager = PipelineManager([BrokenStageInTest(event_bus=bus)], event_bus=bus)
    manager.execute(context)

    event_names = [ev.name for ev in emitted_events]
    assert EVENT_PROCESSING_FAILED in event_names


# ---------------------------------------------------------------------------
# تست‌های Integration Layer (سیستم افزونه‌ها و رجیستری)
# ---------------------------------------------------------------------------

def test_integration_registry_custom_components():
    """بررسی صحت ثبت و بازیابی کامپوننت‌های سفارشی در IntegrationRegistry."""
    registry = IntegrationRegistry()

    @registry.register_ai_provider("test_ai")
    class TestAIProvider(PassthroughProcessor):
        pass

    @registry.register_feed_source("test_feed")
    class TestFeedSource(FakeFetcher):
        pass

    @registry.register_media_processor("test_media")
    class TestMediaProcessor(PassthroughMediaProcessor):
        pass

    assert registry.get_ai_provider("test_ai") == TestAIProvider
    assert registry.get_feed_source("test_feed") == TestFeedSource
    assert registry.get_media_processor("test_media") == TestMediaProcessor


def test_integration_plugin_initialization():
    """بررسی تعریف، ثبت و مقداردهی اولیه یک پلاگین سفارشی."""
    registry = IntegrationRegistry()
    bus = EventBus(enabled=True, logging_enabled=False)

    class MyCustomPlugin(IntegrationPlugin):
        def __init__(self):
            self.initialized_with_bus = None
            self.event_called = False

        @property
        def plugin_name(self) -> str:
            return "my_custom_plugin"

        def initialize(self, event_bus: EventBus) -> None:
            self.initialized_with_bus = event_bus
            event_bus.subscribe(EVENT_CONTENT_RECEIVED, self.on_content_received)

        def on_content_received(self, event: PipelineEvent):
            self.event_called = True

    plugin = MyCustomPlugin()
    registry.register_plugin(plugin.plugin_name, plugin)
    plugin.initialize(bus)

    assert registry.get_plugin("my_custom_plugin") == plugin
    assert plugin.initialized_with_bus == bus

    # تست انتشار رویداد و تأثیر آن روی افزونه
    bus.publish(PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="test:1"))
    assert plugin.event_called is True
