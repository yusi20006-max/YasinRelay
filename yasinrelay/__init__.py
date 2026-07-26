"""
yasinrelay
پروژه‌ای که محتوا را از کانال‌های تلگرام دریافت می‌کند (با همان مکانیزم
OpenFeed: دور زدن فیلترینگ از طریق translate.goog domain fronting)، با
AI پردازش می‌کند، و در ایتا منتشر می‌کند.
"""

from .ai_processor import CallableProcessor, ContentProcessor, PassthroughProcessor, ProcessedContent
from .config import EitaaConfig, RelayConfig, load_config
from .eitaa_publisher import EitaaPublisher, PublishError, PublishResult
from .fetch_engine import FakeFetcher, FetchEngine, FetchError, Post, SubprocessFetcher
from .pipeline import ChannelRunReport, Pipeline

__all__ = [
    "CallableProcessor",
    "ContentProcessor",
    "PassthroughProcessor",
    "ProcessedContent",
    "EitaaConfig",
    "RelayConfig",
    "load_config",
    "EitaaPublisher",
    "PublishError",
    "PublishResult",
    "FakeFetcher",
    "FetchEngine",
    "FetchError",
    "Post",
    "SubprocessFetcher",
    "ChannelRunReport",
    "Pipeline",
]

__version__ = "0.1.0"
