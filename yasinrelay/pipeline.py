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
from .event_bus import EventBus, get_event_bus

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
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._fetch_engine = fetch_engine
        self._processor = processor
        self._publisher = publisher
        self._db = database
        self._media_processor = media_processor or PassthroughMediaProcessor()
        self._event_bus = event_bus or get_event_bus()

        # راه‌اندازی مراحل موتور پایپ‌لاین جدید برای حفظ سازگاری و ارتباط با Event Bus
        self._collector = CollectorStage(self._fetch_engine, event_bus=self._event_bus)
        self._pipeline_manager = PipelineManager([
            NormalizerStage(event_bus=self._event_bus),
            ValidatorStage(event_bus=self._event_bus),
            DuplicateDetectionStage(self._db, event_bus=self._event_bus),
            AIProcessorStage(self._processor, event_bus=self._event_bus),
            MediaProcessorStage(self._media_processor, event_bus=self._event_bus),
            PublisherStage(self._publisher, self._db, event_bus=self._event_bus),
        ], event_bus=self._event_bus)

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
        try:
            reports = [self.run_channel(channel, limit=limit) for channel in channels]

            # هماهنگ‌سازی و ثبت وضعیت با YasinHub در پایان اجرا
            total_fetched = sum(r.fetched for r in reports)
            total_published = sum(r.published for r in reports)
            all_errors = []
            for r in reports:
                all_errors.extend(r.errors)

            success = len(all_errors) == 0
            if success:
                msg = f"{total_published} پست با موفقیت منتشر شد (از {total_fetched} پست دریافت شده)"
            else:
                msg = f"خطا در رله پست‌ها: {', '.join(all_errors[:3])}"
                if len(all_errors) > 3:
                    msg += " ..."

            try:
                from .hub_integration import report_hub_status
                report_hub_status(success=success, message=msg)
            except Exception as e:
                logger.warning(f"خطا در ثبت وضعیت در YasinHub: {e}")

            return reports
        except Exception as exc:
            msg = f"خطای بحرانی در اجرای پایپ‌لاین: {exc}"
            try:
                from .hub_integration import report_hub_status
                report_hub_status(success=False, message=msg)
            except Exception:
                pass
            raise exc
