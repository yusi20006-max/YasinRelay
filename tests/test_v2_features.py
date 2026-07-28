"""
test_v2_features.py
پوشش تست برای امکانات جدید نسخه ۲ هسته YasinRelay شامل:
- لایه ذخیره‌سازی SQLite
- تشخیص پست‌های تکراری
- سیستم زمان‌بند (Scheduler)
- تنظیمات توسعه‌یافته
- لاگینگ
"""

from datetime import datetime
import os
import shutil
import logging
import time
from unittest.mock import Mock, patch

import pytest

from yasinrelay.storage.database import Database
from yasinrelay.storage.models import DBPost
from yasinrelay.config import load_config
from yasinrelay.logging_config import setup_logging
from yasinrelay.scheduler import Scheduler
from yasinrelay.pipeline import Pipeline, calculate_content_hash
from yasinrelay.fetch_engine import FakeFetcher, Post
from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig


# ---------------------------------------------------------------------------
# تست‌های لایه ذخیره‌سازی (Storage Layer)
# ---------------------------------------------------------------------------

def test_database_initialization():
    db = Database(":memory:")
    # بررسی تهی نبودن اتصال دیتابیس حافظه‌ای
    assert db._get_connection() is not None
    db.close()


def test_database_save_and_get_post():
    db = Database(":memory:")
    post = DBPost(
        id=None,
        source="@test_channel",
        source_message_id="12345",
        content_hash="abcde12345",
        title="عنوان تست",
        content="محتوای تست",
        media="http://example.com/image.jpg",
        status="pending",
        created_at=datetime.now(),
    )

    saved = db.save_post(post)
    assert saved.id is not None

    retrieved = db.get_post("@test_channel", "12345")
    assert retrieved is not None
    assert retrieved.source == "@test_channel"
    assert retrieved.source_message_id == "12345"
    assert retrieved.content_hash == "abcde12345"
    assert retrieved.title == "عنوان تست"
    assert retrieved.content == "محتوای تست"
    assert retrieved.media == "http://example.com/image.jpg"
    assert retrieved.status == "pending"
    db.close()


def test_database_exists():
    db = Database(":memory:")
    post = DBPost(
        id=None,
        source="@test_channel",
        source_message_id="12345",
        content_hash="abcde12345",
        title=None,
        content="محتوای تست",
        media=None,
        status="pending",
        created_at=datetime.now(),
    )
    db.save_post(post)

    # تست وجود بر اساس منبع و شناسه
    assert db.exists("@test_channel", "12345") is True
    # تست عدم وجود
    assert db.exists("@test_channel", "99999") is False

    # تست وجود بر اساس منبع، شناسه و هش محتوا
    assert db.exists("@test_channel", "12345", "abcde12345") is True
    assert db.exists("@another", "12345", "abcde12345") is True  # یافتن بر اساس هش محتوا

    db.close()


def test_database_mark_published():
    db = Database(":memory:")
    post = DBPost(
        id=None,
        source="@test_channel",
        source_message_id="12345",
        content_hash="abcde12345",
        title=None,
        content="تست",
        media=None,
        status="pending",
        created_at=datetime.now(),
    )
    db.save_post(post)

    success = db.mark_published("@test_channel", "12345")
    assert success is True

    retrieved = db.get_post("@test_channel", "12345")
    assert retrieved.status == "published"
    assert retrieved.published_at is not None

    # تلاش برای مارک کردن یک پست ناموجود
    assert db.mark_published("@test_channel", "99999") is False
    db.close()


def test_database_list_recent_posts():
    db = Database(":memory:")
    for i in range(5):
        post = DBPost(
            id=None,
            source="@test_channel",
            source_message_id=str(i),
            content_hash=f"hash_{i}",
            title=None,
            content=f"محتوای {i}",
            media=None,
            status="pending",
            created_at=datetime.now(),
        )
        db.save_post(post)

    recent = db.list_recent_posts(limit=3)
    assert len(recent) == 3
    assert recent[0].source_message_id == "4"  # آخرین اضافه شده
    db.close()


# ---------------------------------------------------------------------------
# تست‌های تشخیص پست‌های تکراری (Duplicate Detection)
# ---------------------------------------------------------------------------

def test_pipeline_ignores_duplicate_posts():
    db = Database(":memory:")
    fetcher = FakeFetcher()
    post = Post(channel="@news", message_id="1", text="تست یکتا")
    fetcher.add_posts("@news", [post])

    processor = PassthroughProcessor()
    config = EitaaConfig(token="TOKEN", channel="@eitaa")
    publisher = EitaaPublisher(config)

    pipeline = Pipeline(fetcher, processor, publisher, database=db)

    with patch("requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=200, text="ok")

        # اجرای اول: پست باید ارسال شود
        report1 = pipeline.run_channel("@news")
        assert report1.fetched == 1
        assert report1.published == 1
        assert mock_post.call_count == 1

        # بررسی ثبت در دیتابیس با وضعیت موفقیت‌آمیز
        db_post = db.get_post("@news", "1")
        assert db_post is not None
        assert db_post.status == "published"

        # اجرای دوم: پست تکراری نباید ارسال شود
        report2 = pipeline.run_channel("@news")
        assert report2.fetched == 1
        assert report2.published == 0
        assert mock_post.call_count == 1  # تعداد کل فراخوانی‌ها تغییر نکرده است


# ---------------------------------------------------------------------------
# تست‌های سیستم زمان‌بند (Scheduler System)
# ---------------------------------------------------------------------------

def test_scheduler_runs_task_periodically():
    task_runs = 0

    def dummy_task():
        nonlocal task_runs
        task_runs += 1
        # بعد از ۲ بار اجرا متوقف شود
        if task_runs >= 2:
            scheduler.stop()

    # بازه زمانی ۱ ثانیه‌ای برای تست سریع
    scheduler = Scheduler(interval_seconds=1, task=dummy_task)

    start_time = time.time()
    scheduler.start()
    end_time = time.time()

    assert task_runs >= 2
    assert end_time - start_time >= 1


# ---------------------------------------------------------------------------
# تست‌های تنظیمات توسعه‌یافته (Configuration Improvements)
# ---------------------------------------------------------------------------

@patch.dict(os.environ, {
    "DATABASE_PATH": "custom_relay.db",
    "LOG_LEVEL": "DEBUG",
    "SCHEDULE_INTERVAL": "900",
    "AI_PROVIDER": "openai"
})
def test_extended_configuration_loading():
    cfg = load_config()
    assert cfg.database_path == "custom_relay.db"
    assert cfg.log_level == "DEBUG"
    assert cfg.schedule_interval == 900
    assert cfg.ai_provider == "openai"


# ---------------------------------------------------------------------------
# تست‌های لاگینگ (Logging Configuration)
# ---------------------------------------------------------------------------

def test_logging_setup_creates_files():
    # تضمین عدم تداخل با فایل‌های لاگ جاری با ریست کردن پوشه تستی در صورت امکان
    log_dir = "logs"
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir, ignore_errors=True)

    setup_logging(log_level="INFO")

    logger = logging.getLogger("yasin_test")
    logger.info("تست لاگ اطلاعات")
    logger.error("تست لاگ خطا")

    assert os.path.exists("logs/relay.log")
    assert os.path.exists("logs/error.log")

    with open("logs/relay.log", "r", encoding="utf-8") as f:
        relay_content = f.read()
        assert "تست لاگ اطلاعات" in relay_content
        assert "تست لاگ خطا" in relay_content

    with open("logs/error.log", "r", encoding="utf-8") as f:
        error_content = f.read()
        assert "تست لاگ اطلاعات" not in error_content
        assert "تست لاگ خطا" in error_content
