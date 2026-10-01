"""Persistent deduplication using SQLite.

Ensures each user is notified at most once per message (identified by
channel_id + message_ts). Survives bot restarts. Uses INSERT OR IGNORE
with a PRIMARY KEY constraint for natural idempotence.

Key design:
- Idempotence key: (channel_id, message_ts, user_id)
- message_ts = thread_ts if the message is in a thread, else the message's own ts
- WAL mode for better concurrent read/write behavior
- Old records cleaned up via retention policy

Limitations:
- Single-instance only (SQLite file lock). For multi-instance, use
  PostgreSQL or a shared store.
- No atomicity between Slack API call and DB write. Strategy:
  1. Check dedup before sending to Slack
  2. Send to Slack
  3. If Slack succeeds, mark in DB. If DB fails, log error
     (Slack redelivery will cause a re-check, which is acceptable)
  4. If Slack fails, do NOT mark in DB (retry on next event)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

from group_bot.logger import truncate_id, truncate_ts

log = structlog.get_logger("group_bot.dedup")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS notifications_sent (
    channel_id   TEXT NOT NULL,
    message_ts   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (channel_id, message_ts, user_id)
) WITHOUT ROWID;
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_notifications_created_at
ON notifications_sent(created_at);
"""


class DedupStore:
    """SQLite-backed deduplication store.

    Thread-safe via SQLite's internal locking. Uses WAL mode for
    concurrent reads during writes.
    """

    def __init__(self, db_path: str | Path):
        """Initialize the dedup store, creating the database if needed.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,  # autocommit mode
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_INDEX)

        log.info(
            "dedup_store_initialized",
            db_path=str(self._db_path),
        )

    def is_notified(self, channel_id: str, message_ts: str, user_id: str) -> bool:
        """Check if a user has already been notified for a specific message.

        Args:
            channel_id: Slack channel ID.
            message_ts: Slack message timestamp (thread_ts or message ts).
            user_id: Slack user ID.

        Returns:
            True if the user was already notified for this message.
        """
        cur = self._conn.execute(
            "SELECT 1 FROM notifications_sent "
            "WHERE channel_id = ? AND message_ts = ? AND user_id = ?",
            (channel_id, message_ts, user_id),
        )
        result = cur.fetchone() is not None
        if result:
            log.info(
                "already_notified",
                channel_id=truncate_id(channel_id),
                message_ts=truncate_ts(message_ts),
                user_id=truncate_id(user_id),
            )
        return result

    def mark_notified(self, channel_id: str, message_ts: str, user_id: str) -> bool:
        """Mark a user as notified for a specific message.

        Uses INSERT OR IGNORE for idempotence. If the record already
        exists, this is a no-op.

        Args:
            channel_id: Slack channel ID.
            message_ts: Slack message timestamp.
            user_id: Slack user ID.

        Returns:
            True if a new record was inserted, False if it already existed.
        """
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO notifications_sent (channel_id, message_ts, user_id) "
            "VALUES (?, ?, ?)",
            (channel_id, message_ts, user_id),
        )
        inserted = cur.rowcount > 0

        if inserted:
            log.info(
                "marked_notified",
                channel_id=truncate_id(channel_id),
                message_ts=truncate_ts(message_ts),
                user_id=truncate_id(user_id),
            )
        else:
            log.warning(
                "mark_notified_already_exists",
                channel_id=truncate_id(channel_id),
                message_ts=truncate_ts(message_ts),
                user_id=truncate_id(user_id),
            )

        return inserted

    def mark_notified_batch(
        self, channel_id: str, message_ts: str, user_ids: list[str]
    ) -> list[str]:
        """Mark multiple users as notified in a single transaction.

        Args:
            channel_id: Slack channel ID.
            message_ts: Slack message timestamp.
            user_ids: List of Slack user IDs.

        Returns:
            List of user IDs that were newly inserted (not already present).
        """
        newly_inserted: list[str] = []
        self._conn.execute("BEGIN")
        try:
            for uid in user_ids:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO notifications_sent "
                    "(channel_id, message_ts, user_id) VALUES (?, ?, ?)",
                    (channel_id, message_ts, uid),
                )
                if cur.rowcount > 0:
                    newly_inserted.append(uid)
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

        log.info(
            "marked_notified_batch",
            channel_id=truncate_id(channel_id),
            message_ts=truncate_ts(message_ts),
            total=len(user_ids),
            newly_inserted=len(newly_inserted),
        )

        return newly_inserted

    def cleanup_old_records(self, days: int) -> int:
        """Delete dedup records older than the specified number of days.

        Args:
            days: Number of days to retain.

        Returns:
            Number of records deleted.
        """
        cur = self._conn.execute(
            "DELETE FROM notifications_sent "
            "WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        deleted = cur.rowcount
        if deleted > 0:
            log.info("cleanup_old_records", deleted=deleted, retention_days=days)
        return deleted

    def get_stats(self) -> dict[str, int]:
        """Return basic statistics about the dedup store.

        Returns:
            Dict with total record count.
        """
        cur = self._conn.execute("SELECT COUNT(*) FROM notifications_sent")
        total = cur.fetchone()[0]
        return {"total_records": total}

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        log.info("dedup_store_closed")
