"""
pipeline_engine.py
موتور پیشرفته و ماژولار پایپ‌لاین نسخه ۲ (Pipeline Engine) برای مدیریت کل جریان:
Collector -> Normalizer -> Validator -> Duplicate Detection -> AI Processor -> Media Processor -> Publisher
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .ai_processor import ContentProcessor, ProcessedContent
from .eitaa_publisher import EitaaPublisher, PublishResult
from .fetch_engine import FetchEngine, Post
from .media_processor import MediaProcessor
from .storage.database import Database
from .storage.models import DBPost
from .event_bus import (
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

    def __init__(self, fetch_engine: FetchEngine, event_bus: Optional[EventBus] = None) -> None:
        self.fetch_engine = fetch_engine
        self.event_bus = event_bus or get_event_bus()

    def collect(self, channel: str, limit: int = 10) -> List[PipelineContext]:
        logger.info(f"[Collector] شروع دریافت پست‌ها برای کانال: {channel} با محدودیت: {limit}")
        posts = self.fetch_engine.fetch(channel, limit=limit)
        logger.info(f"[Collector] تعداد {len(posts)} پست دریافت شد.")

        contexts = []
        for post in posts:
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        PipelineEvent(
                            name=EVENT_CONTENT_RECEIVED,
                            content_id=f"{post.channel}:{post.message_id}",
                            payload={"post": asdict(post)},
                            metadata={},
                        )
                    )
                except Exception as exc:
                    logger.error(f"[Collector] خطا در انتشار رویداد ContentReceived: {exc}", exc_info=True)
            contexts.append(PipelineContext(post=post))
        return contexts


class NormalizerStage(PipelineStage):
    """مرحله نرمال‌سازی (Normalizer) - پاک‌سازی متن و فیلدها."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or get_event_bus()

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        logger.debug(f"[Normalizer] نرمال‌سازی متن برای پست: {context.post.message_id}")
        # حذف فاصله‌های اضافی در ابتدا و انتها و نرمال‌سازی ساده فاصله
        text = context.processed_text.strip()
        context.processed_text = text

        if self.event_bus:
            try:
                self.event_bus.publish(
                    PipelineEvent(
                        name=EVENT_CONTENT_NORMALIZED,
                        content_id=f"{context.post.channel}:{context.post.message_id}",
                        payload={"processed_text": context.processed_text},
                        metadata=context.metadata,
                    )
                )
            except Exception as exc:
                logger.error(f"[Normalizer] خطا در انتشار رویداد ContentNormalized: {exc}", exc_info=True)

        return context


class ValidatorStage(PipelineStage):
    """مرحله اعتبارسنجی (Validator) - بررسی ساختار و صحت محتوا."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or get_event_bus()

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

    def __init__(self, database: Optional[Database], event_bus: Optional[EventBus] = None) -> None:
        self.db = database
        self.event_bus = event_bus or get_event_bus()

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
                if self.event_bus:
                    try:
                        self.event_bus.publish(
                            PipelineEvent(
                                name=EVENT_DUPLICATE_DETECTED,
                                content_id=f"{context.post.channel}:{context.post.message_id}",
                                payload={"content_hash": content_hash, "is_duplicate": True},
                                metadata=context.metadata,
                            )
                        )
                    except Exception as exc:
                        logger.error(f"[DuplicateDetection] خطا در انتشار رویداد DuplicateDetected: {exc}", exc_info=True)
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

    def __init__(self, processor: ContentProcessor, event_bus: Optional[EventBus] = None) -> None:
        self.processor = processor
        self.event_bus = event_bus or get_event_bus()

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

            if self.event_bus:
                try:
                    self.event_bus.publish(
                        PipelineEvent(
                            name=EVENT_AI_PROCESSING_COMPLETED,
                            content_id=f"{context.post.channel}:{context.post.message_id}",
                            payload={
                                "processed_text": context.processed_text,
                                "summary": processed_content.summary,
                            },
                            metadata=context.metadata,
                        )
                    )
                except Exception as exc:
                    logger.error(f"[AIProcessor] خطا در انتشار رویداد AIProcessingCompleted: {exc}", exc_info=True)
        except Exception as exc:
            err_msg = f"خطا در پردازش هوش مصنوعی مرحله: {exc}"
            logger.error(err_msg, exc_info=True)
            context.errors.append(err_msg)
            # خطا در AI پردازش را متوقف نمی‌کند، به متن اصلی بازمی‌گردیم
        return context


class MediaProcessorStage(PipelineStage):
    """مرحله پردازش رسانه (Media Processor)."""

    def __init__(self, media_processor: MediaProcessor, event_bus: Optional[EventBus] = None) -> None:
        self.media_processor = media_processor
        self.event_bus = event_bus or get_event_bus()

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        if context.processed_media_url:
            logger.info(f"[MediaProcessor] پردازش رسانه برای پست: {context.post.message_id}")
            try:
                # به صورت پیش‌فرض از متد پردازش تصویر استفاده می‌کنیم؛ بسته به فرمت قابل توسعه است
                processed_url = self.media_processor.process_image(context.processed_media_url)
                context.processed_media_url = processed_url

                if self.event_bus:
                    try:
                        self.event_bus.publish(
                            PipelineEvent(
                                name=EVENT_MEDIA_PROCESSING_COMPLETED,
                                content_id=f"{context.post.channel}:{context.post.message_id}",
                                payload={"processed_media_url": context.processed_media_url},
                                metadata=context.metadata,
                            )
                        )
                    except Exception as exc:
                        logger.error(f"[MediaProcessor] خطا در انتشار رویداد MediaProcessingCompleted: {exc}", exc_info=True)
            except Exception as exc:
                err_msg = f"خطا در پردازش رسانه مرحله: {exc}"
                logger.error(err_msg, exc_info=True)
                context.errors.append(err_msg)
        return context


class PublisherStage(PipelineStage):
    """مرحله انتشار در ایتا (Publisher)."""

    def __init__(self, publisher: EitaaPublisher, database: Optional[Database], event_bus: Optional[EventBus] = None) -> None:
        self.publisher = publisher
        self.db = database
        self.event_bus = event_bus or get_event_bus()

    def process(self, context: PipelineContext) -> PipelineContext:
        if not context.is_valid or context.is_duplicate:
            return context

        logger.info(f"[Publisher] شروع انتشار پست {context.post.message_id} در ایتا")

        if self.event_bus:
            try:
                self.event_bus.publish(
                    PipelineEvent(
                        name=EVENT_PUBLISHING_STARTED,
                        content_id=f"{context.post.channel}:{context.post.message_id}",
                        payload={
                            "processed_text": context.processed_text,
                            "processed_media_url": context.processed_media_url,
                        },
                        metadata=context.metadata,
                    )
                )
            except Exception as exc:
                logger.error(f"[Publisher] خطا در انتشار رویداد PublishingStarted: {exc}", exc_info=True)

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

                if self.event_bus:
                    try:
                        self.event_bus.publish(
                            PipelineEvent(
                                name=EVENT_PUBLISHING_COMPLETED,
                                content_id=f"{context.post.channel}:{context.post.message_id}",
                                payload={"published_success": True},
                                metadata=context.metadata,
                            )
                        )
                    except Exception as exc:
                        logger.error(f"[Publisher] خطا در انتشار رویداد PublishingCompleted: {exc}", exc_info=True)
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

    def __init__(self, stages: List[PipelineStage], event_bus: Optional[EventBus] = None) -> None:
        self.stages = stages
        self.event_bus = event_bus or get_event_bus()

    def execute(self, context: PipelineContext) -> PipelineContext:
        """اجرای تمام مراحل ثبت‌شده به ترتیب روی کانتکست ورودی با مدیریت خطاها."""
        current_ctx = context

        if self.event_bus:
            try:
                self.event_bus.publish(
                    PipelineEvent(
                        name=EVENT_PROCESSING_STARTED,
                        content_id=f"{context.post.channel}:{context.post.message_id}",
                        payload={"context": asdict(context)},
                        metadata=context.metadata,
                    )
                )
            except Exception as exc:
                logger.error(f"[PipelineManager] خطا در انتشار رویداد ProcessingStarted: {exc}", exc_info=True)

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

                if self.event_bus:
                    try:
                        self.event_bus.publish(
                            PipelineEvent(
                                name=EVENT_PROCESSING_FAILED,
                                content_id=f"{current_ctx.post.channel}:{current_ctx.post.message_id}",
                                payload={"errors": current_ctx.errors, "is_valid": current_ctx.is_valid},
                                metadata=current_ctx.metadata,
                            )
                        )
                    except Exception as e_exc:
                        logger.error(f"[PipelineManager] خطا در انتشار رویداد ProcessingFailed: {e_exc}", exc_info=True)
                break

        # اگر در پایان اجرای پایپ‌لاین خطایی در کانتکست وجود داشته باشد یا نامعتبر باشد
        if (not current_ctx.is_valid or current_ctx.errors) and self.event_bus:
            try:
                self.event_bus.publish(
                    PipelineEvent(
                        name=EVENT_PROCESSING_FAILED,
                        content_id=f"{current_ctx.post.channel}:{current_ctx.post.message_id}",
                        payload={"errors": current_ctx.errors, "is_valid": current_ctx.is_valid},
                        metadata=current_ctx.metadata,
                    )
                )
            except Exception as exc:
                logger.error(f"[PipelineManager] خطا در انتشار رویداد ProcessingFailed در انتهای پردازش: {exc}", exc_info=True)

        return current_ctx
