"""Tests for SQLite deduplication store."""

import os
import time

import pytest

from group_bot.modules.groups.dedup import DedupStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_state.sqlite3"
    s = DedupStore(db_path)
    yield s
    s.close()


class TestDedupStore:
    def test_mark_notified_new(self, store):
        result = store.mark_notified("C001", "1700000.000100", "U0001")
        assert result is True

    def test_mark_notified_duplicate(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        result = store.mark_notified("C001", "1700000.000100", "U0001")
        assert result is False

    def test_is_notified_true(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        assert store.is_notified("C001", "1700000.000100", "U0001") is True

    def test_is_notified_false(self, store):
        assert store.is_notified("C001", "1700000.000100", "U0001") is False

    def test_different_users_same_message(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        assert store.is_notified("C001", "1700000.000100", "U0001") is True
        assert store.is_notified("C001", "1700000.000100", "U0002") is False

    def test_different_messages_same_user(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        assert store.is_notified("C001", "1700000.000100", "U0001") is True
        assert store.is_notified("C001", "1700000.000200", "U0001") is False

    def test_different_channels_same_user_message(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        assert store.is_notified("C001", "1700000.000100", "U0001") is True
        assert store.is_notified("C002", "1700000.000100", "U0001") is False

    def test_persistence_across_reconnect(self, tmp_path):
        db_path = tmp_path / "test_persist.sqlite3"
        store1 = DedupStore(db_path)
        store1.mark_notified("C001", "1700000.000100", "U0001")
        store1.close()

        store2 = DedupStore(db_path)
        assert store2.is_notified("C001", "1700000.000100", "U0001") is True
        store2.close()

    def test_batch_mark(self, store):
        new = store.mark_notified_batch("C001", "1700000.000100", ["U0001", "U0002", "U0003"])
        assert new == ["U0001", "U0002", "U0003"]
        assert len(new) == 3

    def test_batch_mark_with_duplicates(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        new = store.mark_notified_batch("C001", "1700000.000100", ["U0001", "U0002"])
        assert new == ["U0002"]

    def test_batch_mark_all_duplicates(self, store):
        store.mark_notified_batch("C001", "1700000.000100", ["U0001", "U0002"])
        new = store.mark_notified_batch("C001", "1700000.000100", ["U0001", "U0002"])
        assert new == []

    def test_batch_mark_empty_list(self, store):
        new = store.mark_notified_batch("C001", "1700000.000100", [])
        assert new == []

    def test_cleanup_old_records(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")

        store._conn.execute(
            "UPDATE notifications_sent SET created_at = datetime('now', '-100 days') "
            "WHERE channel_id = 'C001' AND message_ts = '1700000.000100'"
        )

        deleted = store.cleanup_old_records(days=90)
        assert deleted == 1
        assert store.is_notified("C001", "1700000.000100", "U0001") is False

    def test_cleanup_keeps_recent_records(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        deleted = store.cleanup_old_records(days=90)
        assert deleted == 0
        assert store.is_notified("C001", "1700000.000100", "U0001") is True

    def test_get_stats(self, store):
        store.mark_notified_batch("C001", "1700000.000100", ["U0001", "U0002"])
        stats = store.get_stats()
        assert stats["total_records"] == 2

    def test_db_file_created(self, store, tmp_path):
        assert (tmp_path / "test_state.sqlite3").exists()

    def test_creates_parent_directory(self, tmp_path):
        db_path = tmp_path / "subdir" / "nested" / "state.sqlite3"
        s = DedupStore(db_path)
        s.mark_notified("C001", "1700000.000100", "U0001")
        s.close()
        assert db_path.exists()

    def test_thread_ts_as_message_ts(self, store):
        store.mark_notified("C001", "1700000.000100", "U0001")
        assert store.is_notified("C001", "1700000.000100", "U0001") is True
        assert store.is_notified("C001", "1700000.000200", "U0001") is False
