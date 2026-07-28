"""
test_v2_pipeline_engine.py
تست‌های جامع برای موتور پایپ‌لاین نسخه ۲ (Pipeline Engine) پروژه YasinRelay.
"""

from datetime import datetime
import time
from unittest.mock import Mock, patch

import pytest

from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.eitaa_publisher import EitaaPublisher, EitaaConfig
from yasinrelay.fetch_engine import FakeFetcher, Post
from yasinrelay.media_processor import PassthroughMediaProcessor
from yasinrelay.pipeline_engine import (
    AIProcessorStage,
    CollectorStage,
    DuplicateDetectionStage,
    MediaProcessorStage,
    NormalizerStage,
    PipelineContext,
    PipelineManager,
    PipelineStage,
    PublisherStage,
    ValidatorStage,
)
from yasinrelay.storage.database import Database
from yasinrelay.storage.models import DBPost


# ---------------------------------------------------------------------------
# تست‌های موفقیت‌آمیز مراحل پایپ‌لاین (Success Flows)
# ---------------------------------------------------------------------------

def test_pipeline_engine_success_flow():
    db = Database(":memory:")
    fetcher = FakeFetcher()
    post = Post(channel="@test_news", message_id="101", text="  محتوای خام تستی با فاصله  ")
    fetcher.add_posts("@test_news", [post])

    # تعریف استیج‌ها
    collector = CollectorStage(fetcher)
    contexts = collector.collect("@test_news", limit=1)
    assert len(contexts) == 1

    context = contexts[0]

    stages = [
        NormalizerStage(),
        ValidatorStage(),
        DuplicateDetectionStage(db),
        AIProcessorStage(PassthroughProcessor()),
        MediaProcessorStage(PassthroughMediaProcessor()),
    ]

    manager = PipelineManager(stages)
    result_ctx = manager.execute(context)

    # بررسی اجرای نرمالایزر
    assert result_ctx.processed_text == "محتوای خام تستی با فاصله"
    assert result_ctx.is_valid is True
    assert result_ctx.is_duplicate is False

    # بررسی ثبت به عنوان pending در دیتابیس
    db_post = db.get_post("@test_news", "101")
    assert db_post is not None
    assert db_post.status == "pending"
    db.close()


# ---------------------------------------------------------------------------
# تست مدیریت خطای استیج‌ها (Stage Error Handling)
# ---------------------------------------------------------------------------

class BrokenStage(PipelineStage):
    def process(self, context: PipelineContext) -> PipelineContext:
        raise RuntimeError("خطای شبیه‌سازی‌شده در استیج")


def test_pipeline_engine_stage_failure_recovery():
    db = Database(":memory:")
    post = Post(channel="@test", message_id="1", text="متن")
    context = PipelineContext(post=post)

    manager = PipelineManager([
        NormalizerStage(),
        BrokenStage(),  # این استیج خراب است
        PublisherStage(EitaaPublisher(EitaaConfig("", "")), db),  # نباید اجرا شود
    ])

    result_ctx = manager.execute(context)

    # پایپ‌لاین باید خطا را ثبت کرده و وضعیت معتبر بودن را غیرفعال کند
    assert result_ctx.is_valid is False
    assert len(result_ctx.errors) == 1
    assert "خطای شبیه‌سازی‌شده" in result_ctx.errors[0]
    assert result_ctx.published_success is False
    db.close()


# ---------------------------------------------------------------------------
# تست تشخیص و مدیریت پست‌های تکراری
# ---------------------------------------------------------------------------

def test_pipeline_engine_duplicate_check_and_skip():
    db = Database(":memory:")
    fetcher = FakeFetcher()
    post = Post(channel="@my_channel", message_id="5", text="محتوای کاملا یکسان")
    fetcher.add_posts("@my_channel", [post])

    stages = [
        NormalizerStage(),
        ValidatorStage(),
        DuplicateDetectionStage(db),
    ]
    manager = PipelineManager(stages)

    # اجرای اول: ثبت در دیتابیس
    context1 = PipelineContext(post=post)
    result1 = manager.execute(context1)
    assert result1.is_duplicate is False

    # اجرای دوم: تشخیص تکراری بودن
    context2 = PipelineContext(post=post)
    result2 = manager.execute(context2)
    assert result2.is_duplicate is True
    db.close()


# ---------------------------------------------------------------------------
# تست ادغام زمان‌بند و سازگاری با گذشته (Scheduler Integration & Backward Compat)
# ---------------------------------------------------------------------------

@patch("yasinrelay.eitaa_publisher.requests.post")
def test_pipeline_backward_compatibility(mock_post):
    mock_post.return_value = Mock(status_code=200, text="ok")
    db = Database(":memory:")

    fetcher = FakeFetcher()
    post = Post(channel="@news", message_id="44", text="خبر جدید")
    fetcher.add_posts("@news", [post])

    from yasinrelay.pipeline import Pipeline
    pipeline = Pipeline(
        fetch_engine=fetcher,
        processor=PassthroughProcessor(),
        publisher=EitaaPublisher(EitaaConfig("TOKEN", "@chan")),
        database=db,
    )

    # اجرای کامل لوله برای کانال جهت سنجش سازگاری کلاس Pipeline
    report = pipeline.run_channel("@news")
    assert report.fetched == 1
    assert report.published == 1
    assert len(report.errors) == 0

    # بررسی دیتابیس برای وضعیت نهایی انتشار
    db_post = db.get_post("@news", "44")
    assert db_post is not None
    assert db_post.status == "published"
    db.close()
