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
from .event_bus import (
    PipelineEvent,
    EventBus,
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
from .integration import IntegrationPlugin, IntegrationRegistry, integration_registry
from .router import (
    BaseTransport,
    EitaaTransport,
    MockTransport,
    RoutingRule,
    ChannelRule,
    KeywordRule,
    RegexRule,
    MessageRouter,
    EVENT_ROUTING_STARTED,
    EVENT_ROUTE_MATCHED,
    EVENT_ROUTE_SKIPPED,
    EVENT_ROUTE_FAILED,
    EVENT_DELIVERY_COMPLETED,
    EVENT_DELIVERY_FAILED,
)

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
    # رویدادها و گذرگاه رویداد
    "PipelineEvent",
    "EventBus",
    "get_event_bus",
    "EVENT_CONTENT_RECEIVED",
    "EVENT_CONTENT_NORMALIZED",
    "EVENT_DUPLICATE_DETECTED",
    "EVENT_PROCESSING_STARTED",
    "EVENT_AI_PROCESSING_COMPLETED",
    "EVENT_MEDIA_PROCESSING_COMPLETED",
    "EVENT_PUBLISHING_STARTED",
    "EVENT_PUBLISHING_COMPLETED",
    "EVENT_PROCESSING_FAILED",
    # لایه یکپارچه‌سازی و افزونه‌ها
    "IntegrationPlugin",
    "IntegrationRegistry",
    "integration_registry",
    # هدایت پیام و انتقال
    "BaseTransport",
    "EitaaTransport",
    "MockTransport",
    "RoutingRule",
    "ChannelRule",
    "KeywordRule",
    "RegexRule",
    "MessageRouter",
    "EVENT_ROUTING_STARTED",
    "EVENT_ROUTE_MATCHED",
    "EVENT_ROUTE_SKIPPED",
    "EVENT_ROUTE_FAILED",
    "EVENT_DELIVERY_COMPLETED",
    "EVENT_DELIVERY_FAILED",
]

__version__ = "2.0.0"
