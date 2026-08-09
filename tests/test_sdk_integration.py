"""
test_sdk_integration.py
تست‌های ادغام و عملکرد برای هماهنگی YasinRelay با Yasin-Core SDK.
"""

from __future__ import annotations

import pytest
import sqlite3
from unittest.mock import patch, Mock
from yasin_core.sdk import YasinCoreClient, active_context, get_current_context
from yasinrelay.ai_processor import PassthroughProcessor, Post
from yasinrelay.pipeline import Pipeline
from yasinrelay.fetch_engine import FakeFetcher
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig
from yasinrelay.storage.database import Database
from yasinrelay.event_bus import EventBus as RelayEventBus


def test_sdk_client_initialization():
    """تست مقداردهی اولیه کلاینت SDK در YasinRelay."""
    client = YasinCoreClient()
    assert client is not None
    assert isinstance(client.version, str) and client.version


def test_context_creation_and_propagation():
    """تست ایجاد کانتکست و انتشار آن در کلاینت SDK."""
    client = YasinCoreClient()
    ctx = client.create_context({"env": "test-env", "pipeline": "yasinrelay"})

    with active_context(ctx):
        current_ctx = get_current_context()
        assert current_ctx.get("env") == "test-env"
        assert current_ctx.get("pipeline") == "yasinrelay"


def test_memory_usage_through_sdk():
    """تست مدیریت حافظه (بلندمدت و کوتاه‌مدت) به کمک کلاینت SDK."""
    client = YasinCoreClient()

    client.save_memory("key1", "val1", category="short-term")
    client.save_memory("key2", "val2", category="long-term")

    assert client.get_memory("key1", category="short-term") == "val1"
    assert client.get_memory("key2", category="long-term") == "val2"


def test_tool_execution_through_sdk():
    """تست اجرای ابزارها (Tools) به کمک کلاینت SDK."""
    client = YasinCoreClient()

    from yasin_core.sdk import tool

    @tool(name="format_post_for_eitaa", description="Formats text for Eitaa publishing")
    def format_post(text: str) -> str:
        return f"[Eitaa Channel] {text}"

    client.register_tool(format_post)

    assert "format_post_for_eitaa" in client.list_tools()
    assert client.get_tool("format_post_for_eitaa") == format_post

    result = client.execute_tool("format_post_for_eitaa", text="محتوای تستی")
    assert result == "[Eitaa Channel] محتوای تستی"


@patch("requests.post")
def test_relay_runtime_and_message_routing_with_sdk(mock_post):
    """تست هماهنگی لایه پیام‌رسان و اجرای پایپ‌لاین رله به همراه ساختارهای زمینه SDK."""
    mock_post.return_value = Mock(status_code=200, text='{"ok": true}')

    # ۱. تعریف فچر و ناشر و دیتابیس حافظه‌ای رله
    fetcher = FakeFetcher()
    fetcher.add_posts("@telegram_news", [Post(channel="@telegram_news", message_id="1", text="پست جدید تستی")])

    config = EitaaConfig(token="fake_token", channel="@eitaa_chan")
    publisher = EitaaPublisher(config, inter_message_delay_seconds=0)
    db = Database(db_path=":memory:")
    relay_bus = RelayEventBus()
    processor = PassthroughProcessor()

    # ۲. راه‌اندازی پایپ‌لاین رله
    pipeline = Pipeline(
        fetch_engine=fetcher,
        processor=processor,
        publisher=publisher,
        database=db,
        event_bus=relay_bus
    )

    # ۳. استفاده از کلاینت و کانتکست SDK برای مدیریت وضعیت رله در فرآیند اجرا
    client = YasinCoreClient()
    sdk_ctx = client.create_context({
        "pipeline_id": "yasinrelay-e2e-pipeline",
        "status": "initializing"
    })

    with active_context(sdk_ctx):
        # تغییر وضعیت سلامت/گزارش به کمک کانتکست فعال SDK
        get_current_context().set("status", "running")

        # اجرای پایپ‌لاین دریافت و هدایت پیام
        report = pipeline.run_channel("@telegram_news", limit=1)

        # اعتبارسنجی گزارش نهایی و ارسال‌های رله
        assert report.fetched == 1
        assert report.published == 1
        assert len(report.errors) == 0

        # ثبت وضعیت نهایی و گزارش سلامت در دیتابیس/کانتکست
        get_current_context().set("status", "completed")
        assert get_current_context().get("status") == "completed"

    db.close()
