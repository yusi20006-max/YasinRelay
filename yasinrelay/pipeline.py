"""
pipeline.py
اتصال سه مرحله‌ی اصلی: دریافت (fetch) -> پردازش با AI (process) ->
انتشار در ایتا (publish).

هر سه جزء (FetchEngine, ContentProcessor, EitaaPublisher) از طریق
dependency injection وارد Pipeline می‌شوند تا تست‌پذیر بمانند و بدون
نیاز به سرویس‌های واقعی (باینری Go، API ایتا) قابل آزمایش باشند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .ai_processor import ContentProcessor
from .eitaa_publisher import EitaaPublisher, PublishResult
from .fetch_engine import FetchEngine, FetchError, Post


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
    ) -> None:
        self._fetch_engine = fetch_engine
        self._processor = processor
        self._publisher = publisher

    def run_channel(self, channel: str, limit: int = 10) -> ChannelRunReport:
        report = ChannelRunReport(channel=channel)

        try:
            posts: List[Post] = self._fetch_engine.fetch(channel, limit=limit)
        except FetchError as exc:
            report.errors.append(str(exc))
            return report

        report.fetched = len(posts)

        for post in posts:
            processed = self._processor.process(post)
            result: PublishResult = self._publisher.publish(processed)
            if result.success:
                report.published += 1
            else:
                report.errors.append(result.error or "خطای نامشخص در انتشار")

        return report

    def run(self, channels: List[str], limit: int = 10) -> List[ChannelRunReport]:
        return [self.run_channel(channel, limit=limit) for channel in channels]
