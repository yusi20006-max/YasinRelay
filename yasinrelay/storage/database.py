"""
database.py
مدیریت و ارتباط با پایگاه‌داده SQLite برای ذخیره‌سازی پست‌ها.
"""

from __future__ import annotations

import sqlite3
import logging
from datetime import datetime
from typing import List, Optional

from .models import DBPost

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "relay.db") -> None:
        self.db_path = db_path
        self._conn = None
        if db_path == ":memory:":
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            logger.error(f"خطا در ایجاد اتصال به پایگاه‌داده '{self.db_path}': {exc}", exc_info=True)
            raise

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    media TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    published_at TIMESTAMP,
                    UNIQUE(source, source_message_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_content_hash ON posts(content_hash)"
            )
            conn.commit()
        except sqlite3.Error as exc:
            logger.error(f"خطا در ساختاردهی پایگاه‌داده: {exc}", exc_info=True)
            raise
        finally:
            if self._conn is None:
                conn.close()

    def save_post(self, post: DBPost) -> DBPost:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO posts (
                    id, source, source_message_id, content_hash, title, content, media, status, created_at, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.id,
                    post.source,
                    post.source_message_id,
                    post.content_hash,
                    post.title,
                    post.content,
                    post.media,
                    post.status,
                    post.created_at.isoformat() if post.created_at else datetime.now().isoformat(),
                    post.published_at.isoformat() if post.published_at else None,
                ),
            )
            conn.commit()
            if post.id is None:
                post.id = cursor.lastrowid
            return post
        except sqlite3.Error as exc:
            logger.error(f"خطا در ذخیره‌سازی پست در پایگاه‌داده: {exc}", exc_info=True)
            raise
        finally:
            if self._conn is None:
                conn.close()

    def get_post(self, source: str, source_message_id: str) -> Optional[DBPost]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM posts WHERE source = ? AND source_message_id = ?",
                (source, source_message_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_post(row)
        except sqlite3.Error as exc:
            logger.error(f"خطا در دریافت پست از پایگاه‌داده: {exc}", exc_info=True)
            raise
        finally:
            if self._conn is None:
                conn.close()

    def exists(self, source: str, source_message_id: str, content_hash: Optional[str] = None) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if content_hash:
                cursor.execute(
                    "SELECT 1 FROM posts WHERE (source = ? AND source_message_id = ?) OR content_hash = ?",
                    (source, source_message_id, content_hash),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM posts WHERE source = ? AND source_message_id = ?",
                    (source, source_message_id),
                )
            return cursor.fetchone() is not None
        except sqlite3.Error as exc:
            logger.error(f"خطا در بررسی وجود پست در پایگاه‌داده: {exc}", exc_info=True)
            raise
        finally:
            if self._conn is None:
                conn.close()

    def mark_published(self, source: str, source_message_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE posts
                SET status = 'published', published_at = ?
                WHERE source = ? AND source_message_id = ?
                """,
                (datetime.now().isoformat(), source, source_message_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            logger.error(f"خطا در به‌روزرسانی وضعیت انتشار پست در پایگاه‌داده: {exc}", exc_info=True)
            raise
        finally:
            if self._conn is None:
                conn.close()

    def list_recent_posts(self, limit: int = 50) -> List[DBPost]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            return [self._row_to_post(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error(f"خطا در دریافت لیست پست‌های اخیر از پایگاه‌داده: {exc}", exc_info=True)
            raise
        finally:
            if self._conn is None:
                conn.close()

    def _row_to_post(self, row: sqlite3.Row) -> DBPost:
        created_at_val = row["created_at"]
        published_at_val = row["published_at"]

        created_at = datetime.fromisoformat(created_at_val) if created_at_val else datetime.now()
        published_at = datetime.fromisoformat(published_at_val) if published_at_val else None

        return DBPost(
            id=row["id"],
            source=row["source"],
            source_message_id=row["source_message_id"],
            content_hash=row["content_hash"],
            title=row["title"],
            content=row["content"],
            media=row["media"],
            status=row["status"],
            created_at=created_at,
            published_at=published_at,
        )

    def close(self) -> None:
        """بستن اتصال در صورت وجود."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
