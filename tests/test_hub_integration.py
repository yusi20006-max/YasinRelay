"""
test_hub_integration.py
تست‌های لایه یکپارچه‌سازی با YasinHub و کلاس YasinRelayClient.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yasin_relay.sdk import YasinRelayClient
from yasinrelay.hub_integration import report_hub_status
from yasinrelay.pipeline import Pipeline, ChannelRunReport
from yasinrelay.fetch_engine import FakeFetcher, Post
from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig
from yasinrelay.storage.database import Database
from yasinrelay.storage.models import DBPost
from yasinrelay.event_bus import get_event_bus, PipelineEvent


@pytest.fixture
def temp_env_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        original_env = os.environ.get("YASIN_STATUS_DIR")
        os.environ["YASIN_STATUS_DIR"] = tmpdir
        yield Path(tmpdir)
        if original_env is not None:
            os.environ["YASIN_STATUS_DIR"] = original_env
        else:
            os.environ.pop("YASIN_STATUS_DIR", None)


@pytest.fixture
def test_db():
    # ساخت دیتابیس موقت در حافظه برای تست‌ها
    db = Database(":memory:")
    yield db
    db.close()


def test_report_hub_status_fallback(temp_env_dir):
    # تست نوشتن مستقیم در فایل وضعیت زمانی که کتابخانه yasinhub نصب نیست
    with patch.dict(sys.modules, {"yasinhub": None, "yasinhub.status_store": None}):
        report_hub_status(success=True, message="۱۰ پست رله شد")

        status_file = temp_env_dir / "yasinrelay.json"
        assert status_file.exists()

        data = json.loads(status_file.read_text(encoding="utf-8"))
        assert data["success"] is True
        assert data["message"] == "۱۰ پست رله شد"
        assert "last_run" in data


def test_report_hub_status_yasinhub_integration(temp_env_dir):
    # تست ثبت وضعیت از طریق تابع اصلی YasinHub
    mock_write_status = MagicMock()
    mock_status_store = MagicMock()
    mock_status_store.write_status = mock_write_status

    with patch.dict(sys.modules, {"yasinhub": mock_status_store, "yasinhub.status_store": mock_status_store}):
        report_hub_status(success=False, message="خطا در ارتباط با ایتا")
        mock_write_status.assert_called_once_with("yasinrelay", success=False, message="خطا در ارتباط با ایتا")


def test_yasin_relay_client_connect(test_db):
    # اتصال کلاینت با تایید وجود دیتابیس
    with patch("yasin_relay.sdk.Database", return_value=test_db):
        client = YasinRelayClient()
        assert client.connect() is True


def test_yasin_relay_client_get_status(test_db):
    # آماده‌سازی دیتابیس فرضی
    post1 = DBPost(
        id=1,
        source="src",
        source_message_id="1",
        content_hash="h1",
        title="title1",
        content="content1",
        media=None,
        status="published",
        created_at=datetime.now()
    )
    post2 = DBPost(
        id=2,
        source="src",
        source_message_id="2",
        content_hash="h2",
        title="title2",
        content="content2",
        media=None,
        status="failed",
        created_at=datetime.now()
    )
    test_db.save_post(post1)
    test_db.save_post(post2)

    with patch("yasin_relay.sdk.Database", return_value=test_db):
        with patch("subprocess.run") as mock_run:
            # شبیه‌سازی در حال اجرا بودن پروسس رله
            mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")

            client = YasinRelayClient()
            status = client.get_status()

            assert status["status"] == "active"
            assert status["processed_messages"] == 2
            assert status["published_messages"] == 1
            assert isinstance(status["source_channels"], list)


def test_yasin_relay_client_handle_event():
    client = YasinRelayClient()
    bus = get_event_bus()

    received_events = []
    def on_event(event):
        received_events.append(event)

    bus.subscribe("test_external_event", on_event)
    try:
        success = client.handle_event("test_external_event", {"content_id": "123", "data": "hello"})
        assert success is True
        assert len(received_events) == 1
        assert received_events[0].name == "test_external_event"
        assert received_events[0].content_id == "123"
        assert received_events[0].payload["data"] == "hello"
    finally:
        bus.unsubscribe("test_external_event", on_event)


def test_pipeline_run_syncs_status(temp_env_dir, test_db):
    # شبیه‌سازی یک پایپ‌لاین و بررسی تغییر وضعیت نهایی YasinHub
    fetcher = FakeFetcher()
    fetcher.add_posts("@news", [Post(channel="@news", message_id="1", text="پست اول")])
    processor = PassthroughProcessor()
    config = EitaaConfig(token="fake", channel="@fake")
    publisher = EitaaPublisher(config, inter_message_delay_seconds=0)

    # شبیه‌سازی درخواست‌های خروجی ایتا
    with patch("yasinrelay.eitaa_publisher.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text='{"ok": true}')

        pipeline = Pipeline(
            fetch_engine=fetcher,
            processor=processor,
            publisher=publisher,
            database=test_db
        )

        with patch.dict(sys.modules, {"yasinhub": None, "yasinhub.status_store": None}):
            reports = pipeline.run(["@news"], limit=10)

            assert len(reports) == 1
            assert reports[0].fetched == 1
            assert reports[0].published == 1

            status_file = temp_env_dir / "yasinrelay.json"
            assert status_file.exists()

            data = json.loads(status_file.read_text(encoding="utf-8"))
            assert data["success"] is True
            assert "1 پست با موفقیت منتشر شد" in data["message"]
