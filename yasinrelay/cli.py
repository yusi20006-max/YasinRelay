"""
cli.py
اجرای pipeline از خط فرمان.

اجرای معمولی `run` قبل از شروع، تنظیمات را تعاملی دریافت می‌کند و در `.env`
ذخیره می‌کند. در اجراهای بعدی Enter کردن هر فیلد مقدار قبلی را نگه می‌دارد.
برای سرویس‌ها و اجرای بدون ترمینال از `--non-interactive` استفاده کنید.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import List, Optional

from .ai_processor import ContentProcessor
from .config import configure_interactively, load_config
from .eitaa_publisher import EitaaPublisher
from .fetch_engine import FetchEngine, SubprocessFetcher
from .pipeline import ChannelRunReport, Pipeline
from .storage.database import Database
from .yasinai_adapter import build_content_processor

logger = logging.getLogger(__name__)


def build_pipeline(
    fetch_engine: Optional[FetchEngine] = None,
    processor: Optional[ContentProcessor] = None,
    database: Optional[Database] = None,
) -> Pipeline:
    config = load_config()
    fetch_engine = fetch_engine or SubprocessFetcher()
    processor = processor or build_content_processor(
        ai_provider=config.ai_provider,
        api_key=config.ai_api_key,
        base_url=config.ai_base_url,
        model=config.ai_model,
    )
    publisher = EitaaPublisher(config.eitaa, config.inter_message_delay_seconds)
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

    run_parser = subparsers.add_parser("run", help="اجرای pipeline با تنظیمات ذخیره‌شده")
    run_parser.add_argument("--channel", action="append", dest="channels", help="یک کانال خاص (قابل تکرار)")
    run_parser.add_argument("--limit", type=int, default=10, help="حداکثر تعداد پست هر کانال")
    run_parser.add_argument("--loop", action="store_true", help="اجرای مداوم و دوره‌ای پایپ‌لاین")
    run_parser.add_argument("--schedule", action="store_true", help="اجرای پایپ‌لاین با سیستم زمان‌بند جدید")
    run_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="بدون پرسش؛ فقط از تنظیمات فعلی محیط/.env استفاده کن",
    )

    args = parser.parse_args(argv)

    if args.command != "run":
        return 1

    if not args.non_interactive:
        if not sys.stdin.isatty():
            logger.error("اجرای تعاملی به ترمینال نیاز دارد؛ برای سرویس‌ها از --non-interactive استفاده کنید.")
            return 2
        try:
            configure_interactively()
        except KeyboardInterrupt:
            print("\nاجرای تنظیمات لغو شد.")
            return 130

    config = load_config()

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

    if args.loop:
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

    reports = pipeline.run(channels, limit=args.limit)
    for report in reports:
        _print_report(report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
