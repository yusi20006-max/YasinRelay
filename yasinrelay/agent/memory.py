"""
memory.py
معماری حافظه برای پلتفرم ایجنت شامل انواع حافظه‌های موقت و محاوره‌ای.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseMemory(ABC):
    """رابط پایه‌ی سیستم‌های حافظه."""

    @abstractmethod
    def store(self, key: str, value: Any) -> None:
        """ذخیره مقدار در حافظه."""
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Any:
        """بازیابی مقدار از حافظه."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """پاک‌سازی کامل حافظه."""
        pass


class TaskMemory(BaseMemory):
    """حافظه کوتاه‌مدت متمرکز روی یک تسک مشخص."""

    def __init__(self) -> None:
        self._storage: Dict[str, Any] = {}

    def store(self, key: str, value: Any) -> None:
        self._storage[key] = value

    def retrieve(self, key: str) -> Any:
        return self._storage.get(key)

    def clear(self) -> None:
        self._storage.clear()


class SessionMemory(BaseMemory):
    """حافظه بلندمدت‌تر که در طول یک جلسه اجرایی زنده می‌ماند."""

    def __init__(self) -> None:
        self._storage: Dict[str, Any] = {}

    def store(self, key: str, value: Any) -> None:
        self._storage[key] = value

    def retrieve(self, key: str) -> Any:
        return self._storage.get(key)

    def clear(self) -> None:
        self._storage.clear()


class ConversationMemory(BaseMemory):
    """حافظه تخصصی برای نگه‌داری سابقه گفتگوها (نوبت‌های مکالمه)."""

    def __init__(self) -> None:
        self._messages: List[Dict[str, str]] = []

    def store(self, key: str, value: Any) -> None:
        # در حافظه گفتگو، key می‌تواند نقش فرستنده (مانند user یا assistant) و value متن پیام باشد.
        self._messages.append({"role": key, "content": str(value)})

    def retrieve(self, key: str) -> Any:
        # بازیابی پیام‌ها؛ در صورتی که کلید 'all' باشد، تمام پیام‌ها برگردانده می‌شود.
        if key == "all":
            return self._messages
        return [msg for msg in self._messages if msg["role"] == key]

    def clear(self) -> None:
        self._messages.clear()
