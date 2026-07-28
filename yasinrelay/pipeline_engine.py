"""
pipeline_engine.py
موتور پیشرفته و ماژولار پایپ‌لاین نسخه ۲ (Pipeline Engine) برای مدیریت کل جریان:
Collector -> Normalizer -> Validator -> Duplicate Detection -> AI Processor -> Media Processor -> Publisher
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .ai_processor import ContentProcessor, ProcessedContent
from .eitaa_publisher import EitaaPublisher, PublishResult
from .fetch_engine import FetchEngine, Post
from .media_processor import MediaProcessor
from .storage.database import Database
from .storage.models import DBPost

logger = logging.getLogger(__name__)


def calculate_content_hash(text: str, media_url: Optional[str] = None) -> str:
    """محاسبه هش محتوا برای شناسایی تکراری‌ها."""
    hasher = hashlib.sha256()
    hasher.update((text or "").encode("utf-8"))
    if media_url:
        hasher.update(media_url.encode("utf-8"))
    return hasher.hexdigest()


@dataclass
class PipelineContext:
    """کانتکست اجرای پایپ‌لاین برای نگهداری داده‌ها و وضعیت پردازش یک آیتم."""

    post: Post
    processed_text: str = ""
    processed_media_url: Optional[str] = None
    is_duplicate: bool = False
    is_valid: bool = True
    published_success: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.processed_text:
            self.processed_text = self.post.text
        if self.processed_media_url is None:
            self.processed_media_url = self.post.media_url


class PipelineStage(ABC):
    """کلاس پایه انتزاعی برای مراحل مختلف پایپ‌لاین."""

    @abstractmethod
    def process(self, context: PipelineContext) -> PipelineContext:
        """اجرای عملیات این مرحله روی کانتکست ورودی."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# پیاده‌سازی مراحل مختلف پایپ‌لاین (Stages)
# ---------------------------------------------------------------------------

class CollectorStage:
    """مرحله دریافت پست‌ها (Collector) - پست‌های خام را دریافت کرده و به کانتکست تبدیل می‌کند."""

    def __init__(self, fetch_engine: FetchEngine) -> None:
        self.fetch_engine = fetch_engine

    def collect(self, channel: str, limit: int = 10) -> List[PipelineContext]:
        logger.info(f"[Collector] شروع دریافت پست‌ها برای کانال: {channel} با محدودیت: {limit}")
        posts = self.fetch_engine.fetch(channel, limit=limit)
        logger.info(f"[Collector] تعداد {len(posts)} پست دریافت شد.")
        return [PipelineContext(post=post) for post in posts]


class NormalizerStage(PipelineStage):
    """مرحله نرمال‌سازی (Normalizer) - پاک‌سازی متن و فیلدها."""

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        logger.debug(f"[Normalizer] نرمال‌سازی متن برای پست: {context.post.message_id}")
        # حذف فاصله‌های اضافی در ابتدا و انتها و نرمال‌سازی ساده فاصله
        text = context.processed_text.strip()
        context.processed_text = text
        return context


class ValidatorStage(PipelineStage):
    """مرحله اعتبارسنجی (Validator) - بررسی ساختار و صحت محتوا."""

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        logger.debug(f"[Validator] اعتبارسنجی پست: {context.post.message_id}")
        # پست باید متن یا رسانه داشته باشد
        if not context.processed_text and not context.processed_media_url:
            context.is_valid = False
            msg = f"پست {context.post.message_id} نامعتبر است: متن و رسانه هر دو خالی هستند."
            logger.warning(msg)
            context.errors.append(msg)
        return context


class DuplicateDetectionStage(PipelineStage):
    """مرحله تشخیص تکراری‌ها (Duplicate Detection)."""

    def __init__(self, database: Optional[Database]) -> None:
        self.db = database

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        # محاسبه هش محتوا
        content_hash = calculate_content_hash(context.processed_text, context.processed_media_url)
        context.metadata["content_hash"] = content_hash

        if self.db:
            if self.db.exists(context.post.channel, context.post.message_id, content_hash):
                context.is_duplicate = True
                logger.info(
                    f"[DuplicateDetection] پست تکراری شناسایی شد: {context.post.channel} | شناسه: {context.post.message_id}"
                )
            else:
                # ثبت اولیه در پایگاه داده به صورت pending
                db_post = DBPost(
                    id=None,
                    source=context.post.channel,
                    source_message_id=context.post.message_id,
                    content_hash=content_hash,
                    title=None,
                    content=context.processed_text,
                    media=context.processed_media_url,
                    status="pending",
                    created_at=datetime.now(),
                )
                self.db.save_post(db_post)
        return context


class AIProcessorStage(PipelineStage):
    """مرحله پردازش با هوش مصنوعی (AI Processor)."""

    def __init__(self, processor: ContentProcessor) -> None:
        self.processor = processor

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        logger.info(f"[AIProcessor] شروع پردازش هوش مصنوعی برای پست: {context.post.message_id}")
        try:
            # ایجاد یک پست ساختگی موقت با متن و رسانه پردازش‌شده تا به پردازشگر داده شود
            temp_post = Post(
                channel=context.post.channel,
                message_id=context.post.message_id,
                text=context.processed_text,
                media_url=context.processed_media_url,
                raw=context.post.raw,
            )
            processed_content = self.processor.process(temp_post)
            context.processed_text = processed_content.text
            if processed_content.summary:
                context.metadata["summary"] = processed_content.summary
        except Exception as exc:
            err_msg = f"خطا در پردازش هوش مصنوعی مرحله: {exc}"
            logger.error(err_msg, exc_info=True)
            context.errors.append(err_msg)
            # خطا در AI پردازش را متوقف نمی‌کند، به متن اصلی بازمی‌گردیم
        return context


class MediaProcessorStage(PipelineStage):
    """مرحله پردازش رسانه (Media Processor)."""

    def __init__(self, media_processor: MediaProcessor) -> None:
        self.media_processor = media_processor

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        if context.processed_media_url:
            logger.info(f"[MediaProcessor] پردازش رسانه برای پست: {context.post.message_id}")
            try:
                # به صورت پیش‌فرض از متد پردازش تصویر استفاده می‌کنیم؛ بسته به فرمت قابل توسعه است
                processed_url = self.media_processor.process_image(context.processed_media_url)
                context.processed_media_url = processed_url
            except Exception as exc:
                err_msg = f"خطا در پردازش رسانه مرحله: {exc}"
                logger.error(err_msg, exc_info=True)
                context.errors.append(err_msg)
        return context


class PublisherStage(PipelineStage):
    """مرحله انتشار در ایتا (Publisher)."""

    def __init__(self, publisher: EitaaPublisher, database: Optional[Database]) -> None:
        self.publisher = publisher
        self.db = database

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        logger.info(f"[Publisher] شروع انتشار پست {context.post.message_id} در ایتا")
        try:
            processed_content = ProcessedContent(
                source_post=context.post,
                text=context.processed_text,
                summary=context.metadata.get("summary"),
            )
            # اعمال تغییر رسانه نهایی روی پست منبع برای ناشر
            processed_content.source_post.media_url = context.processed_media_url

            result: PublishResult = self.publisher.publish(processed_content)
            if result.success:
                context.published_success = True
                logger.info(f"[Publisher] پست {context.post.message_id} با موفقیت منتشر شد.")
                if self.db:
                    self.db.mark_published(context.post.channel, context.post.message_id)
            else:
                err_msg = result.error or "خطای نامشخص در انتشار در ایتا"
                logger.error(f"[Publisher] خطا در انتشار پست {context.post.message_id}: {err_msg}")
                context.errors.append(err_msg)
        except Exception as exc:
            err_msg = f"خطای استثنا در مرحله انتشار: {exc}"
            logger.error(err_msg, exc_info=True)
            context.errors.append(err_msg)
        return context


# ---------------------------------------------------------------------------
# مدیریت پایپ‌لاین (Pipeline Manager)
# ---------------------------------------------------------------------------

class PipelineManager:
    """مدیریت و اجرای مراحل مختلف پایپ‌لاین به ترتیب مشخص‌شده."""

    def __init__(self, stages: List[PipelineStage]) -> None:
        self.stages = stages

    def execute(self, context: PipelineContext) -> PipelineContext:
        """اجرای تمام مراحل ثبت‌شده به ترتیب روی کانتکست ورودی با مدیریت خطاها."""
        current_ctx = context
        for stage in self.stages:
            stage_name = stage.__class__.__name__
            logger.debug(f"شروع اجرای مرحله: {stage_name}")
            try:
                current_ctx = stage.process(current_ctx)
            except Exception as exc:
                err_msg = f"خطای پیش‌بینی نشده در مرحله {stage_name}: {exc}"
                logger.error(err_msg, exc_info=True)
                current_ctx.errors.append(err_msg)
                # در صورت وقوع خطا در یک مرحله، برای امنیت بیشتر آیتم معتبر تلقی نمی‌شود
                current_ctx.is_valid = False
                break
        return current_ctx
