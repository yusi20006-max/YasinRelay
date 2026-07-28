"""
pipeline.py
اتصال سه مرحله‌ی اصلی با استفاده از موتور پایپ‌لاین نسخه ۲ (Pipeline Engine):
دریافت (fetch) -> پردازش با AI (process) -> انتشار در ایتا (publish).

این ماژول جهت حفظ سازگاری با نسخه‌های قبلی طراحی شده و به صورت داخلی
از موتور ماژولار پایپ‌لاین نسخه ۲ استفاده می‌کند.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .ai_processor import ContentProcessor
from .eitaa_publisher import EitaaPublisher
from .fetch_engine import FetchEngine, FetchError, Post
from .media_processor import MediaProcessor, PassthroughMediaProcessor
from .pipeline_engine import (
    AIProcessorStage,
    CollectorStage,
    DuplicateDetectionStage,
    MediaProcessorStage,
    NormalizerStage,
    PipelineContext,
    PipelineManager,
    PublisherStage,
    ValidatorStage,
    calculate_content_hash,
)
from .storage.database import Database

logger = logging.getLogger(__name__)


@dataclass
class ChannelRunReport:
    channel: str
    fetched: int = 0
    published: int = 0
    errors: List[str] = field(default_factory=list)


class Pipeline:
    def __init__(
        self,
        fetch_engine: FetchEngine,
        processor: ContentProcessor,
        publisher: EitaaPublisher,
        database: Optional[Database] = None,
        media_processor: Optional[MediaProcessor] = None,
    ) -> None:
        self._fetch_engine = fetch_engine
        self._processor = processor
        self._publisher = publisher
        self._db = database
        self._media_processor = media_processor or PassthroughMediaProcessor()

        # راه‌اندازی مراحل موتور پایپ‌لاین جدید برای حفظ سازگاری
        self._collector = CollectorStage(self._fetch_engine)
        self._pipeline_manager = PipelineManager([
            NormalizerStage(),
            ValidatorStage(),
            DuplicateDetectionStage(self._db),
            AIProcessorStage(self._processor),
            MediaProcessorStage(self._media_processor),
            PublisherStage(self._publisher, self._db),
        ])

    def run_channel(self, channel: str, limit: int = 10) -> ChannelRunReport:
        report = ChannelRunReport(channel=channel)

        try:
            contexts = self._collector.collect(channel, limit=limit)
        except FetchError as exc:
            err_msg = str(exc)
            logger.error(f"خطا در دریافت پست‌ها برای کانال {channel}: {err_msg}")
            report.errors.append(err_msg)
            return report
        except Exception as exc:
            err_msg = f"خطای پیش‌بینی نشده در فاز دریافت برای کانال {channel}: {exc}"
            logger.error(err_msg, exc_info=True)
            report.errors.append(err_msg)
            return report

        report.fetched = len(contexts)

        for context in contexts:
            try:
                result_ctx = self._pipeline_manager.execute(context)
                if result_ctx.published_success:
                    report.published += 1
                if result_ctx.errors:
                    report.errors.extend(result_ctx.errors)
            except Exception as exc:
                err_msg = f"خطای کشف‌نشده در اجرای پایپ‌لاین برای پست {context.post.message_id}: {exc}"
                logger.error(err_msg, exc_info=True)
                report.errors.append(err_msg)

        return report

    def run(self, channels: List[str], limit: int = 10) -> List[ChannelRunReport]:
        return [self.run_channel(channel, limit=limit) for channel in channels]
