"""
tests/test_e2e_integration.py
تست‌های ادغام سرتاسری (End-to-End Integration Tests) برای YasinRelay v1.1.1.
این تست‌ها همگام‌سازی کامل زیر را ارزیابی می‌کنند:
- موتور پایپ‌لاین (Pipeline Engine)
- لایه ذخیره‌سازی SQLite برای حذف تکراری‌ها
- سیستم رویدادهای داخلی (Event Bus) برای ردیابی چرخه حیات
- پردازشگرهای مبتنی بر AI و دانلودر رسانه telemirror
- ناشر نهایی در ایتا
"""

import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch
import pytest
import requests

from yasinrelay.fetch_engine import SubprocessFetcher, FetchError, Post
from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig
from yasinrelay.media_processor import PassthroughMediaProcessor
from yasinrelay.storage.database import Database
from yasinrelay.event_bus import (
    EventBus,
    PipelineEvent,
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
from yasinrelay.pipeline import Pipeline


# ---------------------------------------------------------------------------
# فیوچرهای تستی (Pytest Fixtures)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db():
    """فیوچر دیتابیس موقت حافظه‌ای."""
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def event_bus():
    """فیوچر گذرگاه رویدادها."""
    bus = EventBus(enabled=True, logging_enabled=False)
    yield bus
    bus.clear()


@pytest.fixture
def mock_subprocess_run():
    """فیوچر موک برای subprocess.run جهت شبیه‌سازی باینری Go فچر و دانلودر."""
    with patch("subprocess.run") as mock_run:
        def side_effect(cmd, *args, **kwargs):
            # اگر برای دریافت پست فراخوانی شده است
            if len(cmd) > 1 and "openfeed-fetch" in cmd[0] and "download" not in cmd:
                # شبیه‌سازی خروجی پست خام تلگرام به صورت JSON
                mock_stdout = '[{"message_id": "888", "text": "   محتوای خبر تستی از تلگرام!   ", "media_url": "https://cdn4-telesco-pe.translate.goog/file/photo_888.jpg"}]'
                return Mock(returncode=0, stdout=mock_stdout, stderr="")
            # اگر برای دانلود رسانه با استفاده از telemirror فراخوانی شده است
            elif len(cmd) > 2 and "download" in cmd:
                return Mock(returncode=0, stdout=b"fake-binary-image-data-from-telemirror", stderr="")
            return Mock(returncode=0, stdout=b"", stderr="")

        mock_run.side_effect = side_effect
        yield mock_run


@pytest.fixture
def mock_external_requests():
    """فیوچر موک برای درخواست‌های شبکه (OpenAI API و Eitaayar API)."""
    with patch("requests.post") as mock_post:
        def side_effect(url, *args, **kwargs):
            # شبیه‌سازی فراخوانی هوش مصنوعی OpenAI
            if "chat/completions" in url:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json = lambda: {
                    "choices": [
                        {
                            "message": {
                                "content": "ترجمه و بهبود یافته: محتوای خبر تستی از تلگرام!"
                            }
                        }
                    ]
                }
                return mock_response
            # شبیه‌سازی انتشار در ایتا (Eitaayar API)
            elif "eitaayar.ir/api/" in url:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = '{"ok": true, "result": {"message_id": 9999}}'
                return mock_response

            return Mock(status_code=404, text="Not Found")

        mock_post.side_effect = side_effect
        yield mock_post


# ---------------------------------------------------------------------------
# تست‌های سناریو (Test Cases)
# ---------------------------------------------------------------------------

def test_e2e_successful_pipeline_flow(temp_db, event_bus, mock_subprocess_run, mock_external_requests):
    """
    تست سناریوی موفقیت‌آمیز سرتاسری پایپ‌لاین:
    دریافت -> نرمال‌سازی -> ولیدیشن -> تشخیص تکراری -> پردازش هوش مصنوعی -> دانلود تصویر -> انتشار در ایتا
    همچنین بررسی ترتیب و صحت انتشار رویدادها روی Event Bus.
    """
    # ردیابی رویدادهای منتشرشده روی گذرگاه رویدادها
    emitted_events = []
    def listener(event: PipelineEvent):
        emitted_events.append(event)
    event_bus.subscribe("*", listener)

    # راه‌اندازی فچر، پردازشگر AI، ناشر و موتور پایپ‌لاین کامل
    fetcher = SubprocessFetcher(binary_path="./fetcher/openfeed-fetch")
    processor = PassthroughProcessor(api_key="sk-fakekey")
    config = EitaaConfig(token="EITAATOKEN", channel="@eitaa_chan")
    publisher = EitaaPublisher(config, inter_message_delay_seconds=0)
    media_processor = PassthroughMediaProcessor()

    pipeline = Pipeline(
        fetch_engine=fetcher,
        processor=processor,
        publisher=publisher,
        database=temp_db,
        media_processor=media_processor,
        event_bus=event_bus,
    )

    # اجرای پایپ‌لاین برای کانال فرضی
    report = pipeline.run_channel("@telegram_news", limit=1)

    # ۱. بررسی نتیجه‌ی اجرای پایپ‌لاین
    assert report.fetched == 1
    assert report.published == 1
    assert len(report.errors) == 0

    # ۲. بررسی ذخیره‌سازی وضعیت پست در دیتابیس SQLite به عنوان 'published'
    db_post = temp_db.get_post("@telegram_news", "888")
    assert db_post is not None
    assert db_post.status == "published"
    assert db_post.source_message_id == "888"
    assert db_post.media == "https://cdn4-telesco-pe.translate.goog/file/photo_888.jpg"

    # ۳. بررسی ترتیب و صحت رویدادهای منتشرشده روی Event Bus
    event_names = [ev.name for ev in emitted_events]
    expected_order = [
        EVENT_CONTENT_RECEIVED,
        EVENT_PROCESSING_STARTED,
        EVENT_CONTENT_NORMALIZED,
        EVENT_AI_PROCESSING_COMPLETED,
        EVENT_MEDIA_PROCESSING_COMPLETED,
        EVENT_PUBLISHING_STARTED,
        EVENT_PUBLISHING_COMPLETED
    ]

    for name in expected_order:
        assert name in event_names, f"رویداد {name} در گذرگاه رویدادها منتشر نشده است."

    # بررسی موقعیت مکانی رویدادها برای صحت توالی زمانی اجرای مراحل
    for idx in range(len(expected_order) - 1):
        assert event_names.index(expected_order[idx]) < event_names.index(expected_order[idx + 1]), \
            f"ترتیب انتشار رویدادها رعایت نشده است: {expected_order[idx]} نباید بعد از {expected_order[idx+1]} باشد."

    # ۴. بررسی صحت اطلاعات ارسالی در درخواست انتشار نهایی ایتا (بایت‌های تصویر دانلودشده توسط telemirror)
    # بررسی فراخوانی requests.post برای ارسال فایل به ایتا
    sendFile_calls = [
        call for call in mock_external_requests.call_args_list
        if "sendFile" in call[0][0]
    ]
    assert len(sendFile_calls) == 1
    call_args, call_kwargs = sendFile_calls[0]
    assert "EITAATOKEN" in call_args[0]
    assert call_kwargs["data"]["chat_id"] == "@eitaa_chan"
    assert call_kwargs["data"]["text"] == "ترجمه و بهبود یافته: محتوای خبر تستی از تلگرام!"
    assert call_kwargs["files"] is not None
    assert call_kwargs["files"]["file"][1] == b"fake-binary-image-data-from-telemirror"


def test_e2e_deduplication_on_consecutive_runs(temp_db, event_bus, mock_subprocess_run, mock_external_requests):
    """
    تست سناریوی حذف پست‌های تکراری:
    بررسی اینکه اگر یک پست قبلا منتشر شده باشد، در دور بعدی اجرا نباید به ناشر ارسال شود
    و باید رویداد EVENT_DUPLICATE_DETECTED روی Event Bus منتشر گردد.
    """
    emitted_events = []
    event_bus.subscribe("*", lambda ev: emitted_events.append(ev))

    fetcher = SubprocessFetcher(binary_path="./fetcher/openfeed-fetch")
    processor = PassthroughProcessor(api_key="sk-fakekey")
    config = EitaaConfig(token="EITAATOKEN", channel="@eitaa_chan")
    publisher = EitaaPublisher(config, inter_message_delay_seconds=0)

    pipeline = Pipeline(
        fetch_engine=fetcher,
        processor=processor,
        publisher=publisher,
        database=temp_db,
        event_bus=event_bus,
    )

    # اجرای اول: پست باید با موفقیت منتشر شود
    report1 = pipeline.run_channel("@telegram_news", limit=1)
    assert report1.fetched == 1
    assert report1.published == 1
    assert len(report1.errors) == 0

    # تمیز کردن رویدادها برای ردیابی دقیق اجرای دوم
    emitted_events.clear()
    mock_external_requests.reset_mock()

    # اجرای دوم با همان پست تکراری
    report2 = pipeline.run_channel("@telegram_news", limit=1)
    assert report2.fetched == 1
    assert report2.published == 0  # نباید دوباره منتشر شده باشد
    assert len(report2.errors) == 0

    # بررسی عدم فراخوانی درخواست شبکه برای ایتا در اجرای دوم
    eitaa_calls = [
        call for call in mock_external_requests.call_args_list
        if "eitaayar.ir" in call[0][0]
    ]
    assert len(eitaa_calls) == 0

    # بررسی انتشار رویداد DuplicateDetected
    event_names = [ev.name for ev in emitted_events]
    assert EVENT_DUPLICATE_DETECTED in event_names
    assert EVENT_PUBLISHING_STARTED not in event_names
    assert EVENT_PUBLISHING_COMPLETED not in event_names


def test_e2e_error_isolation_and_graceful_fallback(temp_db, event_bus, mock_subprocess_run, mock_external_requests):
    """
    تست سناریوی مقاومت سیستم و کنترل استثناها:
    بررسی اینکه در صورت وقوع خطای غیرمنتظره در ارتباط با هوش مصنوعی (AI API Failure):
    - سیستم نباید کرش کند.
    - از مکانیزم Fallback متن اصلی (بدون پردازش هوش مصنوعی) استفاده شود و پست منتشر شود.
    همچنین در صورت بروز خطای کلی در بخش ناشر (مثلاً قطعی اینترنت در اتصال به ایتا):
    - رویداد EVENT_PROCESSING_FAILED به همراه جزئیات خطا منتشر شود.
    """
    emitted_events = []
    event_bus.subscribe("*", lambda ev: emitted_events.append(ev))

    # ۱. سناریوی خطای هوش مصنوعی (باید با استفاده از Fallback متن اصلی ارسال شود)
    def broken_api_post(url, *args, **kwargs):
        if "chat/completions" in url:
            # شبیه‌سازی خطای ۵۰۰ سرور OpenAI
            resp = Mock()
            resp.status_code = 500
            resp.text = "Internal Server Error"
            return resp
        elif "eitaayar.ir/api/" in url:
            resp = Mock()
            resp.status_code = 200
            resp.text = '{"ok": true}'
            return resp
        return Mock(status_code=404)

    mock_external_requests.side_effect = broken_api_post

    fetcher = SubprocessFetcher(binary_path="./fetcher/openfeed-fetch")
    processor = PassthroughProcessor(api_key="sk-fakekey")
    config = EitaaConfig(token="EITAATOKEN", channel="@eitaa_chan")
    publisher = EitaaPublisher(config, inter_message_delay_seconds=0)

    pipeline = Pipeline(
        fetch_engine=fetcher,
        processor=processor,
        publisher=publisher,
        database=temp_db,
        event_bus=event_bus,
    )

    report1 = pipeline.run_channel("@telegram_news", limit=1)
    # با وجود شکست AI، به متن اصلی پست fallback کرده و آن را منتشر می‌کند
    assert report1.fetched == 1
    assert report1.published == 1
    assert len(report1.errors) == 0

    # تایید ارسال متن اصلی به ایتا
    eitaa_calls = [
        call for call in mock_external_requests.call_args_list
        if "sendFile" in call[0][0]
    ]
    assert len(eitaa_calls) == 1
    assert eitaa_calls[0][1]["data"]["text"] == "محتوای خبر تستی از تلگرام!"

    # ۲. سناریوی خطای کلی شبکه در زمان ارسال به ایتا (باید رویداد ProcessingFailed شلیک شود)
    # بستن دیتابیس قبلی و باز کردن یکی دیگر برای ایزوله‌سازی کامل تست
    temp_db.close()
    temp_db2 = Database(":memory:")

    # شبیه‌سازی قطعی ارتباط با ایتا
    def connection_error_post(url, *args, **kwargs):
        if "chat/completions" in url:
            resp = Mock()
            resp.status_code = 200
            resp.json = lambda: {"choices": [{"message": {"content": "Translated Text"}}]}
            return resp
        elif "eitaayar.ir" in url:
            raise requests.RequestException("شبکه قطع است")
        return Mock(status_code=404)

    mock_external_requests.side_effect = connection_error_post
    emitted_events.clear()

    pipeline2 = Pipeline(
        fetch_engine=fetcher,
        processor=processor,
        publisher=publisher,
        database=temp_db2,
        event_bus=event_bus,
    )

    report2 = pipeline2.run_channel("@telegram_news", limit=1)
    assert report2.fetched == 1
    assert report2.published == 0
    assert len(report2.errors) > 0  # خطاها ثبت شده باشند

    # بررسی انتشار رویداد ProcessingFailed
    event_names = [ev.name for ev in emitted_events]
    assert EVENT_PROCESSING_FAILED in event_names
    temp_db2.close()
