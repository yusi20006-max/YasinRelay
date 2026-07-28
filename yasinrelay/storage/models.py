"""
models.py
مدل داده‌ی پست ذخیره‌شده در پایگاه‌داده.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DBPost:
    id: Optional[int]
    source: str
    source_message_id: str
    content_hash: str
    title: Optional[str]
    content: Optional[str]
    media: Optional[str]
    status: str
    created_at: datetime
    published_at: Optional[datetime] = None
