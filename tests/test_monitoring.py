"""
test_monitoring.py
تست‌های لایه مانیتورینگ سلامت ران‌تایم و گزارش‌دهی YasinRelay.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from yasin_relay.sdk import YasinRelayClient
from yasinrelay.event_bus import get_event_bus, PipelineEvent, EVENT_CONTENT_RECEIVED, EVENT_PUBLISHING_COMPLETED, EVENT_PROCESSING_FAILED
from yasinrelay.monitoring import HealthMonitor, get_health_monitor
from yasinrelay.storage.database import Database


@pytest.fixture
def monitor():
    # ساخت یک نمونه تمیز از HealthMonitor برای هر تست
    return HealthMonitor()


def test_health_monitor_event_tracking(monitor):
    # بررسی ردیابی اولیه و پیش‌فرض سنجه‌ها
    report = monitor.get_health_report()
    assert report["metrics"]["total_fetched_posts"] == 0
    assert report["metrics"]["total_published_posts"] == 0
    assert report["metrics"]["total_failed_posts"] == 0
    assert report["metrics"]["error_rate_percent"] == 0.0
    assert report["last_run_time"] is None

    # شبیه‌سازی دریافت پست
    event_received = PipelineEvent(name=EVENT_CONTENT_RECEIVED, content_id="chan:1", payload={})
    monitor.on_event(event_received)

    # شبیه‌سازی انتشار موفق پست
    event_published = PipelineEvent(name=EVENT_PUBLISHING_COMPLETED, content_id="chan:1", payload={})
    monitor.on_event(event_published)

    # شبیه‌سازی خطای پردازش پست
    event_failed = PipelineEvent(name=EVENT_PROCESSING_FAILED, content_id="chan:2", payload={"errors": ["خطای ارتباطی سرور"]})
    monitor.on_event(event_failed)

    report = monitor.get_health_report()
    assert report["metrics"]["total_fetched_posts"] == 1
    assert report["metrics"]["total_published_posts"] == 1
    assert report["metrics"]["total_failed_posts"] == 1
    assert report["metrics"]["error_rate_percent"] == 50.0  # (1 / 2) * 100
    assert report["last_run_time"] is not None
    assert report["last_error"]["message"] == "خطای ارتباطی سرور"


def test_health_monitor_database_health_healthy(monitor):
    # دیتابیس معتبر در حافظه
    db = Database(":memory:")
    try:
        report = monitor.get_health_report(database=db)
        assert report["connections"]["database"]["status"] == "connected"
        assert report["connections"]["database"]["error_message"] is None
        assert report["db_stats"]["total_posts"] == 0
    finally:
        db.close()


def test_health_monitor_database_health_error(monitor):
    # شبیه‌سازی دیتابیس دارای خطا
    db = MagicMock()
    db._get_connection.side_effect = Exception("پیغام خطای پایگاه داده آزمایشی")

    report = monitor.get_health_report(database=db)
    assert report["connections"]["database"]["status"] == "error"
    assert "پیغام خطای پایگاه داده آزمایشی" in report["connections"]["database"]["error_message"]
    # وقتی دیتابیس دچار خطا شود، وضعیت کلی سیستم خطا (error) گزارش می‌شود
    assert report["status"] == "error"


@patch("yasinrelay.monitoring.Path.exists")
def test_health_monitor_fetcher_health(mock_exists, monitor):
    # حالت باینری در دسترس
    mock_exists.return_value = True
    report = monitor.get_health_report()
    assert report["connections"]["fetcher"]["status"] == "available"

    # حالت باینری مفقود شده
    mock_exists.return_value = False
    report = monitor.get_health_report()
    assert report["connections"]["fetcher"]["status"] == "unavailable"
    assert "not found on disk" in report["connections"]["fetcher"]["error_message"]


@patch("yasinrelay.monitoring.requests.head")
@patch.dict(os.environ, {"EITAA_TOKEN": "valid-token-123"})
def test_health_monitor_publisher_health_success(mock_head, monitor):
    mock_head.return_value = MagicMock(status_code=200)

    report = monitor.get_health_report()
    assert report["connections"]["publisher"]["status"] == "connected"


@patch("yasinrelay.monitoring.requests.head")
@patch.dict(os.environ, {"EITAA_TOKEN": ""})
def test_health_monitor_publisher_health_missing_token(mock_head, monitor):
    # توکن تعریف نشده
    report = monitor.get_health_report()
    assert report["connections"]["publisher"]["status"] == "degraded"
    assert "token is not configured" in report["connections"]["publisher"]["error_message"]


@patch("yasinrelay.monitoring.requests.head")
@patch.dict(os.environ, {"EITAA_TOKEN": "valid-token-123"})
def test_health_monitor_publisher_health_connection_error(mock_head, monitor):
    mock_head.side_effect = Exception("پاسخی از سرور دریافت نشد")

    report = monitor.get_health_report()
    assert report["connections"]["publisher"]["status"] == "error"
    assert "پاسخی از سرور دریافت نشد" in report["connections"]["publisher"]["error_message"]


def test_get_health_monitor_singleton():
    m1 = get_health_monitor()
    m2 = get_health_monitor()
    assert m1 is m2


@patch("yasin_relay.sdk.Database")
@patch("subprocess.run")
def test_sdk_integration_with_monitoring(mock_run, mock_db_class):
    # بررسی ادغام فیلدهای مانیتورینگ در خروجی get_status کلاینت SDK
    mock_run.return_value = MagicMock(returncode=0, stdout="1234\n")

    db = Database(":memory:")
    mock_db_class.return_value = db
    try:
        client = YasinRelayClient()
        status = client.get_status()

        # بررسی وجود کلیدهای مانیتورینگ جدید
        assert "health" in status
        assert "uptime_seconds" in status
        assert "connections" in status
        assert "metrics" in status
        assert "db_stats" in status
    finally:
        db.close()
