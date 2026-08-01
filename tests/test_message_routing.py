"""
test_message_routing.py
تست‌های جامع برای بخش هدایت هوشمند پیام (Message Routing)، لایه انتقال (Transport) و سازگاری با Yasin-Core SDK.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# ایمپورت‌های هسته Yasin-Core SDK
try:
    from yasin_core.sdk import YasinCoreClient, active_context, get_current_context
    HAS_YASIN_CORE = True
except ImportError:
    HAS_YASIN_CORE = False

from yasinrelay.fetch_engine import Post
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig, PublishResult
from yasinrelay.storage.database import Database
from yasinrelay.event_bus import EventBus, PipelineEvent
from yasinrelay.router import (
    MessageRouter,
    MockTransport,
    EitaaTransport,
    RoutingRule,
    ChannelRule,
    KeywordRule,
    RegexRule,
    EVENT_ROUTING_STARTED,
    EVENT_ROUTE_MATCHED,
    EVENT_ROUTE_SKIPPED,
    EVENT_ROUTE_FAILED,
    EVENT_DELIVERY_COMPLETED,
    EVENT_DELIVERY_FAILED,
)


def test_basic_message_routing_flow():
    """بررسی جریان پایه مسیریابی و تحویل فلو."""
    bus = EventBus(logging_enabled=False)
    router = MessageRouter(event_bus=bus)

    # تعریف بستر انتقال شبیه‌سازی‌شده
    transport_a = MockTransport("transport_a")
    transport_b = MockTransport("transport_b")
    router.register_transport(transport_a)
    router.register_transport(transport_b)

    # تعریف قوانین مسیریابی
    rule_a = ChannelRule("@telegram_news", "transport_a")
    rule_b = ChannelRule("@tech_feed", "transport_b")
    router.add_rule(rule_a)
    router.add_rule(rule_b)

    # پیام ۱: مربوط به کانال telegram_news
    post1 = Post(channel="@telegram_news", message_id="101", text="سلام اخبار جدید")
    assert router.route(post1) is True
    assert len(transport_a.sent_posts) == 1
    assert transport_a.sent_posts[0].message_id == "101"
    assert len(transport_b.sent_posts) == 0

    # پیام ۲: مربوط به کانال tech_feed
    post2 = Post(channel="@tech_feed", message_id="102", text="اخبار تکنولوژی")
    assert router.route(post2) is True
    assert len(transport_b.sent_posts) == 1
    assert transport_b.sent_posts[0].message_id == "102"
    assert len(transport_a.sent_posts) == 1  # همان قبلی

    # پیام ۳: کانال نامشخص (تطابق پیدا نمی‌کند)
    post3 = Post(channel="@unknown_chan", message_id="103", text="متن متفرقه")
    assert router.route(post3) is False
    assert len(transport_a.sent_posts) == 1
    assert len(transport_b.sent_posts) == 1


def test_routing_rules_priority_and_transform():
    """بررسی تطابق قوانین بر اساس اولویت بالا و ترنسفورمرها."""
    router = MessageRouter()
    transport = MockTransport("main_transport")
    router.register_transport(transport)

    # دو قانون مختلف؛ قانون اولویت بالاتر باید اول اجرا شود
    # قانون اولویت پایین (تطابق متن برای کلمه 'مهم')
    rule_low = KeywordRule(["مهم"], "main_transport", priority=5)

    # قانون اولویت بالا (تطابق متن برای کلمه 'فوری') که ترنسفورمر هم دارد
    def urgent_transformer(p: Post) -> Post:
        p.text = f"[فوری] {p.text}"
        return p

    rule_high = RoutingRule(
        name="UrgentRule",
        target_transport="main_transport",
        predicate=lambda p: "فوری" in (p.text or ""),
        transformer=urgent_transformer,
        priority=10
    )

    router.add_rule(rule_low)
    router.add_rule(rule_high)

    # پستی که هر دو کلمه را دارد؛ قانون UrgentRule به علت اولویت ۱۰ باید اعمال شود و ترنسفورمر اجرا شود
    post = Post(channel="@channel_test", message_id="201", text="این یک پیام فوری و بسیار مهم است.")
    assert router.route(post) is True
    assert len(transport.sent_posts) == 1
    assert transport.sent_posts[0].text == "[فوری] این یک پیام فوری و بسیار مهم است."


def test_routing_rules_keyword_and_regex():
    """بررسی صحت عملکرد قوانین KeywordRule و RegexRule."""
    router = MessageRouter()
    transport = MockTransport("dest")
    router.register_transport(transport)

    # قانون کلیدواژه‌ای
    rule_kw = KeywordRule(["تکنولوژی", "برنامه‌نویسی"], "dest", match_any=True)
    router.add_rule(rule_kw)

    # پیام همسان
    post_match = Post(channel="@tech", message_id="1", text="درباره برنامه‌نویسی پایتون")
    assert router.route(post_match) is True

    # پیام ناهمسان
    post_no_match = Post(channel="@tech", message_id="2", text="هوای امروز بارانی است")
    assert router.route(post_no_match) is False

    # قانون ریجکس
    rule_rx = RegexRule(r"^\d{4}-\d{2}-\d{2}", "dest")
    router.add_rule(rule_rx)

    # پیام همسان با ریجکس (فرمت تاریخ در ابتدا)
    post_rx_match = Post(channel="@date", message_id="3", text="2026-08-01: زمان ثبت")
    assert router.route(post_rx_match) is True


def test_routing_error_handling_and_retries():
    """بررسی مدیریت خطاهای ارسال، ذخیره در صف خطا و تلاش مجدد (Reliability)."""
    router = MessageRouter()

    # ایجاد بستر انتقالی که شکست می‌خورد
    bad_transport = MockTransport("broken_link")
    bad_transport.should_fail = True
    bad_transport.failure_reason = "Network Unreachable"
    router.register_transport(bad_transport)

    rule = ChannelRule("@source", "broken_link")
    router.add_rule(rule)

    post = Post(channel="@source", message_id="301", text="محتوای غیرقابل تحویل")

    # هدایت با خطا مواجه می‌شود اما سیستم کرش نمی‌کند
    assert router.route(post) is False

    # بررسی ثبت پیام ناموفق در صف خطا (Dead-Letter Queue)
    failed_msgs = router.get_failed_messages()
    assert len(failed_msgs) == 1
    assert failed_msgs[0]["post"].message_id == "301"
    assert "Network Unreachable" in failed_msgs[0]["error"]

    # برطرف کردن مشکل بستر انتقال و تلاش مجدد
    bad_transport.should_fail = False
    retried_count = router.retry_failed_messages()
    assert retried_count == 1
    assert len(router.get_failed_messages()) == 0
    assert len(bad_transport.sent_posts) == 1
    assert bad_transport.sent_posts[0].message_id == "301"


def test_routing_communication_lifecycle_events():
    """بررسی تولید و انتشار رویدادهای چرخه‌ی حیات مسیریابی در EventBus."""
    bus = EventBus(logging_enabled=False)
    router = MessageRouter(event_bus=bus)

    transport = MockTransport("dest")
    router.register_transport(transport)
    rule = ChannelRule("@source", "dest")
    router.add_rule(rule)

    emitted_events = []
    def log_event(event: PipelineEvent):
        emitted_events.append(event)

    bus.subscribe("*", log_event)

    post = Post(channel="@source", message_id="401", text="یک پیام نمونه")
    assert router.route(post) is True

    # باید حداقل ۳ رویداد رخ داده باشد: RoutingStarted -> RouteMatched -> DeliveryCompleted
    assert len(emitted_events) >= 3
    event_names = [e.name for e in emitted_events]
    assert EVENT_ROUTING_STARTED in event_names
    assert EVENT_ROUTE_MATCHED in event_names
    assert EVENT_DELIVERY_COMPLETED in event_names

    # پیام ۲: بدون قانون مطابقت (RouteSkipped)
    emitted_events.clear()
    post_skipped = Post(channel="@other", message_id="402", text="پیام بدون مقصد")
    assert router.route(post_skipped) is False
    assert len(emitted_events) == 2  # RoutingStarted -> RouteSkipped
    assert emitted_events[0].name == EVENT_ROUTING_STARTED
    assert emitted_events[1].name == EVENT_ROUTE_SKIPPED


@pytest.mark.skipif(not HAS_YASIN_CORE, reason="Yasin-Core SDK is not installed or available")
def test_message_routing_with_yasin_core_sdk():
    """بررسی سازگاری و تعامل MessageRouter با مفاهیم کانتکست و ابزارهای Yasin-Core SDK."""
    client = YasinCoreClient()
    sdk_ctx = client.create_context({
        "environment": "production-validation",
        "routing_policy": "strict"
    })

    db = Database(db_path=":memory:")
    bus = EventBus(logging_enabled=False)
    router = MessageRouter(event_bus=bus, database=db)

    transport = MockTransport("eitaa_channel_validated")
    router.register_transport(transport)

    rule = ChannelRule("@telegram_news", "eitaa_channel_validated")
    router.add_rule(rule)

    post = Post(channel="@telegram_news", message_id="501", text="محتوای مهم اقتصادی")

    with active_context(sdk_ctx):
        # ذخیره گزارش سلامت یا وضعیت مسیریابی در کانتکست SDK
        get_current_context().set("current_routing_msg_id", post.message_id)

        # اجرای عملیات مسیریابی رله
        success = router.route(post)
        assert success is True

        # اعتبارسنجی خروجی بستر انتقال
        assert len(transport.sent_posts) == 1
        assert transport.sent_posts[0].message_id == "501"

        # بررسی ذخیره موفقیت‌آمیز در پایگاه داده SQLite
        assert db.exists(post.channel, post.message_id) is True

        # به‌روزرسانی وضعیت در کانتکست SDK
        get_current_context().set("last_routing_status", "success")
        assert get_current_context().get("last_routing_status") == "success"

    db.close()
