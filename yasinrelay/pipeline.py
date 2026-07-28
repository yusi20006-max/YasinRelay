"""
pipeline.py
اتصال سه مرحله‌ی اصلی: دریافت (fetch) -> پردازش با AI (process) ->
انتشار در ایتا (publish).

هر سه جزء (FetchEngine, ContentProcessor, EitaaPublisher) از طریق
dependency injection وارد Pipeline می‌شوند تا تست‌پذیر بمانند و بدون
نیاز به سرویس‌های واقعی (باینری Go، API ایتا) قابل آزمایش باشند.

در نسخه ۲ هسته، لایه ذخیره‌سازی و بررسی تکراری‌ها اضافه شده است.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .ai_processor import ContentProcessor
from .eitaa_publisher import EitaaPublisher, PublishResult
from .fetch_engine import FetchEngine, FetchError, Post
from .storage.database import Database
from .storage.models import DBPost

logger = logging.getLogger(__name__)


@dataclass
class ChannelRunReport:
    channel: str
    fetched: int = 0
    published: int = 0
    errors: List[str] = field(default_factory=list)


def calculate_content_hash(text: str, media_url: Optional[str] = None) -> str:
    """محاسبه هش محتوا برای شناسایی تکراری‌ها."""
    hasher = hashlib.sha256()
    hasher.update((text or "").encode("utf-8"))
    if media_url:
        hasher.update(media_url.encode("utf-8"))
    return hasher.hexdigest()


class Pipeline:
    def __init__(
        self,
        fetch_engine: FetchEngine,
        processor: ContentProcessor,
        publisher: EitaaPublisher,
        database: Optional[Database] = None,
    ) -> None:
        self._fetch_engine = fetch_engine
        self._processor = processor
        self._publisher = publisher
        self._db = database

    def run_channel(self, channel: str, limit: int = 10) -> ChannelRunReport:
        report = ChannelRunReport(channel=channel)

        logger.info(f"شروع دریافت پست‌ها برای کانال: {channel} با محدودیت: {limit}")
        try:
            posts: List[Post] = self._fetch_engine.fetch(channel, limit=limit)
        except FetchError as exc:
            err_msg = str(exc)
            logger.error(f"خطا در دریافت پست‌ها برای کانال {channel}: {err_msg}")
            report.errors.append(err_msg)
            return report

        report.fetched = len(posts)
        logger.info(f"تعداد {len(posts)} پست دریافت شد.")

        for post in posts:
            content_hash = calculate_content_hash(post.text, post.media_url)

            # بررسی پست‌های تکراری
            if self._db:
                if self._db.exists(post.channel, post.message_id, content_hash):
                    logger.info(
                        f"پست تکراری نادیده گرفته شد. کانال: {post.channel} | شناسه: {post.message_id} | هش: {content_hash}"
                    )
                    continue

                # ذخیره در پایگاه داده به عنوان در حال بررسی/پندینگ
                db_post = DBPost(
                    id=None,
                    source=post.channel,
                    source_message_id=post.message_id,
                    content_hash=content_hash,
                    title=None,
                    content=post.text,
                    media=post.media_url,
                    status="pending",
                    created_at=datetime.now(),
                )
                self._db.save_post(db_post)

            logger.info(f"شروع پردازش هوش مصنوعی برای پست {post.message_id} در {post.channel}")
            try:
                processed = self._processor.process(post)
            except Exception as exc:
                err_msg = f"خطا در پردازش هوش مصنوعی برای پست {post.message_id}: {exc}"
                logger.error(err_msg)
                report.errors.append(err_msg)
                continue

            logger.info(f"شروع انتشار پست {post.message_id} در ایتا")
            try:
                result: PublishResult = self._publisher.publish(processed)
                if result.success:
                    report.published += 1
                    logger.info(f"پست {post.message_id} با موفقیت در ایتا منتشر شد.")
                    if self._db:
                        self._db.mark_published(post.channel, post.message_id)
                else:
                    err_msg = result.error or "خطای نامشخص در انتشار"
                    logger.error(f"خطا در انتشار پست {post.message_id}: {err_msg}")
                    report.errors.append(err_msg)
            except Exception as exc:
                err_msg = f"خطای استثنا در انتشار پست {post.message_id}: {exc}"
                logger.error(err_msg)
                report.errors.append(err_msg)

        return report

    def run(self, channels: List[str], limit: int = 10) -> List[ChannelRunReport]:
        return [self.run_channel(channel, limit=limit) for channel in channels]
