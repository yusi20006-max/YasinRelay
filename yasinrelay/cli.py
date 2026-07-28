"""
cli.py
اجرای pipeline از خط فرمان:

    python -m yasinrelay.cli run
    python -m yasinrelay.cli run --channel @some_channel --limit 5

این ماژول اجزای واقعی (SubprocessFetcher, PassthroughProcessor,
EitaaPublisher) را وصل می‌کند. برای اتصال یک ContentProcessor واقعی
(مثلاً فراخوانی Anthropic API برای ترجمه/خلاصه)، تابع `build_pipeline`
را با یک CallableProcessor دلخواه فراخوانی کنید.
"""

from __future__ import annotations

import argparse
import sys
import time
import logging
from typing import List, Optional

from .ai_processor import ContentProcessor, PassthroughProcessor
from .config import load_config
from .eitaa_publisher import EitaaPublisher
from .fetch_engine import FetchEngine, SubprocessFetcher
from .pipeline import ChannelRunReport, Pipeline
from .storage.database import Database

logger = logging.getLogger(__name__)


def build_pipeline(
    fetch_engine: Optional[FetchEngine] = None,
    processor: Optional[ContentProcessor] = None,
    database: Optional[Database] = None,
) -> Pipeline:
    config = load_config()
    fetch_engine = fetch_engine or SubprocessFetcher()
    processor = processor or PassthroughProcessor(
        api_key=config.ai_api_key,
        base_url=config.ai_base_url,
        model=config.ai_model,
    )
    publisher = EitaaPublisher(config.eitaa, config.inter_message_delay_seconds)

    # راه‌اندازی دیتابیس در صورت عدم ارسال مقدار مستقیم
    if database is None:
        database = Database(config.database_path)

    return Pipeline(fetch_engine, processor, publisher, database=database)


def _print_report(report: ChannelRunReport) -> None:
    logger.info(f"گزارش کانال {report.channel}: دریافت={report.fetched} منتشرشده={report.published}")
    for err in report.errors:
        logger.error(f"  خطا در گزارش کانال {report.channel}: {err}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="yasinrelay")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="اجرای pipeline برای کانال‌های تنظیم‌شده")
    run_parser.add_argument("--channel", action="append", dest="channels", help="یک کانال خاص (قابل تکرار)")
    run_parser.add_argument("--limit", type=int, default=10, help="حداکثر تعداد پست هر کانال")
    run_parser.add_argument("--loop", action="store_true", help="اجرای مداوم و دوره‌ای پایپ‌لاین بر اساس زمان‌بندی قدیم")
    run_parser.add_argument("--schedule", action="store_true", help="اجرای پایپ‌لاین با استفاده از سیستم زمان‌بند جدید")

    args = parser.parse_args(argv)

    if args.command == "run":
        config = load_config()

        # فعال‌سازی سیستم لاگینگ
        from .logging_config import setup_logging
        setup_logging(config.log_level)

        channels = args.channels or config.source_channels
        if not channels:
            logger.error("هیچ کانال منبعی تنظیم نشده است (SOURCE_CHANNELS یا --channel)")
            return 1

        pipeline = build_pipeline()

        if args.schedule:
            logger.info(f"شروع اجرای زمان‌بندی شده. بازه زمانی: {config.schedule_interval} ثانیه")
            from .scheduler import Scheduler

            def run_task():
                logger.info(f"شروع اجرای زمان‌بندی جدید در {time.strftime('%Y-%m-%d %H:%M:%S')}")
                reports = pipeline.run(channels, limit=args.limit)
                for report in reports:
                    _print_report(report)

            scheduler = Scheduler(config.schedule_interval, run_task)
            scheduler.start()
            return 0

        elif args.loop:
            logger.info(f"شروع اجرای دوره‌ای پایپ‌لاین. بازه زمانی: {config.fetch_interval_seconds} ثانیه")
            try:
                while True:
                    logger.info(f"شروع اجرای جدید در {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    reports = pipeline.run(channels, limit=args.limit)
                    for report in reports:
                        _print_report(report)
                    logger.info(f"پایان اجرا. خوابیدن به مدت {config.fetch_interval_seconds} ثانیه...")
                    time.sleep(config.fetch_interval_seconds)
            except KeyboardInterrupt:
                logger.info("اجرای دوره‌ای با دستور کاربر متوقف شد.")
                return 0
        else:
            reports = pipeline.run(channels, limit=args.limit)
            for report in reports:
                _print_report(report)
            return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
