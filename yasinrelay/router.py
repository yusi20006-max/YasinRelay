"""
router.py
سیستم هوشمند هدایت پیام (Message Routing) و لایه انتقال (Transport Layer) در YasinRelay.
این ماژول امکان فیلتر کردن، اولویت‌بندی، تبدیل و ارسال پیام‌ها به مقصدهای مختلف را به همراه مدیریت خطا و تلاش مجدد فراهم می‌کند.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .fetch_engine import Post
from .eitaa_publisher import EitaaPublisher, ProcessedContent, PublishResult
from .storage.database import Database
from .event_bus import EventBus, PipelineEvent, get_event_bus

logger = logging.getLogger(__name__)

# رویدادهای مربوط به مسیریابی و انتقال پیام (Routing and Transport Lifecycle Events)
EVENT_ROUTING_STARTED = "RoutingStarted"
EVENT_ROUTE_MATCHED = "RouteMatched"
EVENT_ROUTE_SKIPPED = "RouteSkipped"
EVENT_ROUTE_FAILED = "RouteFailed"
EVENT_DELIVERY_COMPLETED = "DeliveryCompleted"
EVENT_DELIVERY_FAILED = "DeliveryFailed"


# ---------------------------------------------------------------------------
# لایه انتقال (Transport Layer)
# ---------------------------------------------------------------------------

class BaseTransport(ABC):
    """کلاس انتزاعی پایه برای تمامی بسترهای انتقال پیام (Transports)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """نام منحصربه‌فرد بستر انتقال."""
        raise NotImplementedError

    @abstractmethod
    def send(self, post: Post) -> bool:
        """ارسال یا تحویل پیام به مقصد."""
        raise NotImplementedError


class EitaaTransport(BaseTransport):
    """بستر انتقال پیام به پیام‌رسان ایتا بر اساس EitaaPublisher."""

    def __init__(self, publisher: EitaaPublisher) -> None:
        self.publisher = publisher
        self._name = f"eitaa_{publisher.config.channel.lstrip('@')}"

    @property
    def name(self) -> str:
        return self._name

    def send(self, post: Post) -> bool:
        logger.info(f"[EitaaTransport] در حال ارسال پیام {post.message_id} به کانال {self.publisher.config.channel}")
        processed = ProcessedContent(source_post=post, text=post.text)
        result: PublishResult = self.publisher.publish(processed)
        if not result.success:
            err_msg = result.error or "خطای نامشخص در ناشر ایتا"
            raise RuntimeError(f"شکست در ارسال به ایتا: {err_msg}")
        return True


class MockTransport(BaseTransport):
    """یک بستر انتقال شبیه‌سازی‌شده (Mock) برای اعتبارسنجی و تست‌ها."""

    def __init__(self, name: str = "mock_transport") -> None:
        self._name = name
        self.sent_posts: List[Post] = []
        self.should_fail: bool = False
        self.failure_reason: str = "Mock connection failure"

    @property
    def name(self) -> str:
        return self._name

    def send(self, post: Post) -> bool:
        if self.should_fail:
            raise ConnectionError(self.failure_reason)
        self.sent_posts.append(post)
        logger.info(f"[MockTransport:{self.name}] پیام {post.message_id} با موفقیت تحویل داده شد.")
        return True


# ---------------------------------------------------------------------------
# قوانین مسیریابی (Routing Rules)
# ---------------------------------------------------------------------------

@dataclass
class RoutingRule:
    """قانون مسیریابی پیام بر اساس شرط، ترنسفورمر و اولویت مشخص."""

    name: str
    target_transport: str
    predicate: Callable[[Post], bool]
    transformer: Optional[Callable[[Post], Post]] = None
    priority: int = 0  # اولویت بالاتر زودتر ارزیابی می‌شود

    def match(self, post: Post) -> bool:
        """بررسی تطابق پیام با این قانون."""
        try:
            return self.predicate(post)
        except Exception as exc:
            logger.error(f"[RoutingRule:{self.name}] خطا در ارزیابی شرط قانون: {exc}", exc_info=True)
            return False

    def transform(self, post: Post) -> Post:
        """اعمال تغییرات روی پیام قبل از ارسال در صورت وجود ترنسفورمر."""
        if self.transformer:
            try:
                # کپی سطحی از پست ایجاد می‌کنیم تا تغییرات ایزوله بمانند
                cloned = Post(
                    channel=post.channel,
                    message_id=post.message_id,
                    text=post.text,
                    media_url=post.media_url,
                    raw=post.raw
                )
                return self.transformer(cloned)
            except Exception as exc:
                logger.error(f"[RoutingRule:{self.name}] خطا در تغییر پیام با ترنسفورمر: {exc}", exc_info=True)
        return post


# کارخانه‌های ساخت قوانین آماده (Rule Factory Helpers)

def ChannelRule(channel_name: str, target_transport: str, priority: int = 0) -> RoutingRule:
    """ساخت قانون مسیریابی بر اساس کانال منبع تلگرام."""
    chan = channel_name.lower().strip()
    return RoutingRule(
        name=f"ChannelRule_{chan}",
        target_transport=target_transport,
        predicate=lambda post: post.channel.lower().strip() == chan or post.channel.lower().strip() == f"@{chan.lstrip('@')}",
        priority=priority
    )


def KeywordRule(keywords: List[str], target_transport: str, match_any: bool = True, priority: int = 0) -> RoutingRule:
    """ساخت قانون مسیریابی بر اساس کلمات کلیدی موجود در متن پیام."""
    kws = [k.lower().strip() for k in keywords]
    def predicate(post: Post) -> bool:
        text_lower = (post.text or "").lower()
        if match_any:
            return any(kw in text_lower for kw in kws)
        return all(kw in text_lower for kw in kws)

    return RoutingRule(
        name=f"KeywordRule_{'_'.join(kws[:3])}",
        target_transport=target_transport,
        predicate=predicate,
        priority=priority
    )


def RegexRule(pattern: str, target_transport: str, priority: int = 0) -> RoutingRule:
    """ساخت قانون مسیریابی بر اساس الگوهای باقاعده (Regex)."""
    compiled = re.compile(pattern, re.IGNORECASE)
    return RoutingRule(
        name=f"RegexRule_{pattern[:15]}",
        target_transport=target_transport,
        predicate=lambda post: bool(compiled.search(post.text or "")),
        priority=priority
    )


# ---------------------------------------------------------------------------
# مسیریاب مرکزی پیام (Message Router)
# ---------------------------------------------------------------------------

class MessageRouter:
    """مسیریاب و هدایت‌کننده مرکزی پیام‌ها به مقصدها بر اساس قوانین ثبت‌شده."""

    def __init__(self, event_bus: Optional[EventBus] = None, database: Optional[Database] = None) -> None:
        self.event_bus = event_bus or get_event_bus()
        self.db = database
        self._transports: Dict[str, BaseTransport] = {}
        self._rules: List[RoutingRule] = []
        self._failed_queue: List[Dict[str, Any]] = []  # صف پیام‌های ناموفق جهت افزایش پایایی (Reliability)

    def register_transport(self, transport: BaseTransport) -> None:
        """ثبت یک بستر انتقال جدید."""
        self._transports[transport.name] = transport
        logger.info(f"[MessageRouter] بستر انتقال '{transport.name}' ثبت شد.")

    def get_transport(self, name: str) -> Optional[BaseTransport]:
        """بازیابی بستر انتقال بر اساس نام."""
        return self._transports.get(name)

    def add_rule(self, rule: RoutingRule) -> None:
        """افزودن یک قانون مسیریابی جدید و مرتب‌سازی بر اساس اولویت."""
        self._rules.append(rule)
        # مرتب‌سازی نزولی بر اساس اولویت (priorities بالاتر زودتر تطابق داده می‌شوند)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"[MessageRouter] قانون جدید '{rule.name}' با اولویت {rule.priority} اضافه شد.")

    def route(self, post: Post) -> bool:
        """هدایت و ارسال پیام بر اساس اولین قانون تطبیق‌یافته."""
        content_id = f"{post.channel}:{post.message_id}"
        logger.info(f"[MessageRouter] شروع فرآیند مسیریابی برای پیام {content_id}")

        self._publish_event(EVENT_ROUTING_STARTED, content_id, {"post": post})

        matched_rule: Optional[RoutingRule] = None
        for rule in self._rules:
            if rule.match(post):
                matched_rule = rule
                break

        if not matched_rule:
            logger.info(f"[MessageRouter] هیچ قانونی برای پیام {content_id} تطبیق پیدا نکرد. پیام نادیده گرفته شد.")
            self._publish_event(EVENT_ROUTE_SKIPPED, content_id, {"post": post})
            return False

        logger.info(f"[MessageRouter] قانون '{matched_rule.name}' برای پیام {content_id} تطبیق یافت.")
        self._publish_event(
            EVENT_ROUTE_MATCHED,
            content_id,
            {"rule_name": matched_rule.name, "target_transport": matched_rule.target_transport}
        )

        # دریافت بستر انتقال متناظر
        transport = self.get_transport(matched_rule.target_transport)
        if not transport:
            err_msg = f"بستر انتقال '{matched_rule.target_transport}' یافت نشد."
            logger.error(err_msg)
            self._handle_failure(post, matched_rule, err_msg)
            return False

        # محاسبه هش برای ذخیره‌سازی و تکراری‌یابی در پایگاه داده SQLite در صورت فعال بودن
        if self.db:
            from .pipeline_engine import calculate_content_hash
            content_hash = calculate_content_hash(post.text, post.media_url)
            if self.db.exists(post.channel, post.message_id, content_hash):
                logger.info(f"[MessageRouter] پیام تکراری در پایگاه داده شناسایی شد: {content_id}")
                self._publish_event(EVENT_ROUTE_SKIPPED, content_id, {"post": post, "reason": "duplicate"})
                return False

            # ذخیره اولیه به عنوان pending در پایگاه‌داده
            from .storage.models import DBPost
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
            self.db.save_post(db_post)

        # اعمال تغییر روی پیام در صورت نیاز
        final_post = matched_rule.transform(post)

        try:
            # ارسال پیام از طریق بستر انتقال
            success = transport.send(final_post)
            if success:
                logger.info(f"[MessageRouter] پیام {content_id} با موفقیت از طریق بستر '{transport.name}' ارسال شد.")
                self._publish_event(
                    EVENT_DELIVERY_COMPLETED,
                    content_id,
                    {"transport_name": transport.name}
                )
                # در صورت وجود دیتابیس وضعیت را منتشر شده ثبت می‌کنیم
                if self.db:
                    self.db.mark_published(post.channel, post.message_id)
                return True
        except Exception as exc:
            err_msg = f"خطا در حین ارسال پیام به بستر '{transport.name}': {exc}"
            logger.error(err_msg, exc_info=True)
            self._handle_failure(post, matched_rule, err_msg)

        return False

    def _handle_failure(self, post: Post, rule: RoutingRule, error: str) -> None:
        """مدیریت شرایط تحویل ناموفق و ذخیره‌سازی برای تلاش مجدد یا Dead-Letter."""
        content_id = f"{post.channel}:{post.message_id}"
        self._publish_event(
            EVENT_DELIVERY_FAILED,
            content_id,
            {
                "rule_name": rule.name,
                "target_transport": rule.target_transport,
                "error": error
            }
        )
        self._failed_queue.append({
            "post": post,
            "rule": rule,
            "error": error,
            "timestamp": datetime.now()
        })

    def get_failed_messages(self) -> List[Dict[str, Any]]:
        """بازیابی لیست پیام‌های ناموفق."""
        return self._failed_queue

    def retry_failed_messages(self) -> int:
        """تلاش مجدد برای ارسال پیام‌های ناموفق موجود در صف."""
        if not self._failed_queue:
            logger.info("[MessageRouter] هیچ پیام ناموفقی در صف وجود ندارد.")
            return 0

        logger.info(f"[MessageRouter] شروع تلاش مجدد برای {len(self._failed_queue)} پیام ناموفق.")
        still_failed = []
        success_count = 0

        # یک کپی از صف برمی‌داریم و صف اصلی را خالی می‌کنیم
        items_to_retry = list(self._failed_queue)
        self._failed_queue.clear()

        for item in items_to_retry:
            post: Post = item["post"]
            rule: RoutingRule = item["rule"]
            content_id = f"{post.channel}:{post.message_id}"

            transport = self.get_transport(rule.target_transport)
            if not transport:
                item["error"] = f"بستر انتقال '{rule.target_transport}' یافت نشد."
                still_failed.append(item)
                continue

            # ذخیره اولیه مجدد در دیتابیس در صورت نیاز
            if self.db:
                from .pipeline_engine import calculate_content_hash
                content_hash = calculate_content_hash(post.text, post.media_url)
                if not self.db.exists(post.channel, post.message_id):
                    from .storage.models import DBPost
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
                    self.db.save_post(db_post)

            final_post = rule.transform(post)
            try:
                success = transport.send(final_post)
                if success:
                    success_count += 1
                    logger.info(f"[MessageRouter] [Retry] ارسال مجدد پیام {content_id} با موفقیت انجام شد.")
                    self._publish_event(
                        EVENT_DELIVERY_COMPLETED,
                        content_id,
                        {"transport_name": transport.name, "retry": True}
                    )
                    if self.db:
                        self.db.mark_published(post.channel, post.message_id)
                else:
                    still_failed.append(item)
            except Exception as exc:
                item["error"] = str(exc)
                still_failed.append(item)
                logger.warning(f"[MessageRouter] [Retry] ارسال مجدد پیام {content_id} مجددا شکست خورد: {exc}")

        self._failed_queue = still_failed
        return success_count

    def _publish_event(self, name: str, content_id: str, payload: Dict[str, Any]) -> None:
        """متد کمکی برای انتشار امن رویدادها در گذرگاه رویداد."""
        if self.event_bus:
            try:
                self.event_bus.publish(
                    PipelineEvent(
                        name=name,
                        content_id=content_id,
                        payload=payload,
                        metadata={}
                    )
                )
            except Exception as exc:
                logger.error(f"[MessageRouter] خطا در انتشار رویداد '{name}': {exc}", exc_info=True)
