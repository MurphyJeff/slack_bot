"""Tests for thread notifier module."""

from unittest.mock import MagicMock

import pytest

from group_bot.modules.groups.dedup import DedupStore
from group_bot.modules.groups.notifier import (
    ThreadNotifier,
    compose_message,
    format_mentions,
    resolve_thread_ts,
)


@pytest.fixture
def store(tmp_path):
    s = DedupStore(tmp_path / "test.sqlite3")
    yield s
    s.close()


@pytest.fixture
def mock_slack():
    return MagicMock()


@pytest.fixture
def notifier(store, mock_slack):
    return ThreadNotifier(
        dedup_store=store,
        message_template="cc {mentions}",
        slack_client=mock_slack,
    )


class TestFormatMentions:
    def test_single_user(self):
        assert format_mentions(["U0001"]) == "<@U0001>"

    def test_multiple_users(self):
        assert format_mentions(["U0001", "U0002"]) == "<@U0001> <@U0002>"

    def test_empty_list(self):
        assert format_mentions([]) == ""


class TestComposeMessage:
    def test_cc_template(self):
        result = compose_message("cc {mentions}", ["U0001", "U0002"])
        assert result == "cc <@U0001> <@U0002>"

    def test_custom_template(self):
        result = compose_message("🔔 {mentions} check this!", ["U0001"])
        assert result == "🔔 <@U0001> check this!"

    def test_empty_mentions(self):
        result = compose_message("cc {mentions}", [])
        assert result == "cc "


class TestResolveThreadTs:
    def test_root_message(self):
        event = {"ts": "1700000.000100"}
        assert resolve_thread_ts(event) == "1700000.000100"

    def test_thread_reply(self):
        event = {"ts": "1700000.000200", "thread_ts": "1700000.000100"}
        assert resolve_thread_ts(event) == "1700000.000100"

    def test_missing_ts(self):
        event = {}
        assert resolve_thread_ts(event) == ""


class TestThreadNotifier:
    def test_successful_notification(self, notifier, mock_slack, store):
        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001", "U0002"],
        )
        assert result.posted is True
        assert result.notified_user_ids == ["U0001", "U0002"]
        assert result.skipped_user_ids == []
        mock_slack.post_message.assert_called_once_with(
            channel="C001",
            text="cc <@U0001> <@U0002>",
            thread_ts="1700000.000100",
        )
        assert store.is_notified("C001", "1700000.000100", "U0001") is True
        assert store.is_notified("C001", "1700000.000100", "U0002") is True

    def test_dedup_skips_already_notified(self, notifier, mock_slack, store):
        store.mark_notified("C001", "1700000.000100", "U0001")

        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001", "U0002"],
        )
        assert result.posted is True
        assert result.notified_user_ids == ["U0002"]
        assert result.skipped_user_ids == ["U0001"]
        mock_slack.post_message.assert_called_once_with(
            channel="C001",
            text="cc <@U0002>",
            thread_ts="1700000.000100",
        )

    def test_all_already_notified(self, notifier, mock_slack, store):
        store.mark_notified_batch("C001", "1700000.000100", ["U0001", "U0002"])

        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001", "U0002"],
        )
        assert result.posted is False
        assert result.notified_user_ids == []
        assert result.skipped_user_ids == ["U0001", "U0002"]
        mock_slack.post_message.assert_not_called()

    def test_empty_user_list(self, notifier, mock_slack):
        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=[],
        )
        assert result.posted is False
        assert result.notified_user_ids == []
        mock_slack.post_message.assert_not_called()

    def test_slack_error_does_not_mark_dedup(self, notifier, mock_slack, store):
        mock_slack.post_message.side_effect = Exception("rate_limited")

        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001", "U0002"],
        )
        assert result.posted is False
        assert result.error == "rate_limited"
        assert store.is_notified("C001", "1700000.000100", "U0001") is False
        assert store.is_notified("C001", "1700000.000100", "U0002") is False

    def test_notification_in_thread_reply(self, notifier, mock_slack, store):
        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000200",
            thread_ts="1700000.000100",
            user_ids=["U0001"],
        )
        assert result.posted is True
        assert result.thread_ts == "1700000.000100"
        mock_slack.post_message.assert_called_once_with(
            channel="C001",
            text="cc <@U0001>",
            thread_ts="1700000.000100",
        )

    def test_dedup_persists_after_notifying(self, notifier, mock_slack, store):
        notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001"],
        )
        mock_slack.reset_mock()

        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001"],
        )
        assert result.posted is False
        assert result.skipped_user_ids == ["U0001"]
        mock_slack.post_message.assert_not_called()

    def test_partial_dedup_message_text(self, notifier, mock_slack, store):
        store.mark_notified("C001", "1700000.000100", "U0001")

        result = notifier.notify(
            channel_id="C001",
            message_ts="1700000.000100",
            thread_ts="1700000.000100",
            user_ids=["U0001", "U0002", "U0003"],
        )
        assert result.posted is True
        assert sorted(result.notified_user_ids) == ["U0002", "U0003"]
        assert result.skipped_user_ids == ["U0001"]

        call_args = mock_slack.post_message.call_args
        assert "U0001" not in call_args.kwargs["text"]
        assert "<@U0002>" in call_args.kwargs["text"]
        assert "<@U0003>" in call_args.kwargs["text"]
