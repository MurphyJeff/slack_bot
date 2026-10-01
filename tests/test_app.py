"""Integration tests for the groups module with mocked Slack API."""

import dataclasses
from unittest.mock import MagicMock

import pytest

from group_bot.config import (
    AppConfig,
    FilterConfig,
    GroupEntry,
    NotificationConfig,
    RetentionConfig,
    SlackConfig,
)
from group_bot.modules.groups.dedup import DedupStore
from group_bot.modules.groups.module import GroupsModule


@pytest.fixture
def mock_slack():
    client = MagicMock()
    client.post_message.return_value = {"ok": True, "ts": "1700000.000999"}
    return client


@pytest.fixture
def config():
    return AppConfig(
        slack=SlackConfig(
            mode="socket",
            app_token="xapp-test",
            bot_token="xoxb-test",
            signing_secret="secret",
        ),
        filters=FilterConfig(
            allowed_channel_ids=[],
            ignored_channel_ids=[],
            ignore_bot_messages=True,
            ignore_thread_replies=False,
        ),
        groups={
            "com": [
                GroupEntry(user_id="U0000001", comment="Martine"),
                GroupEntry(user_id="U0000002", comment="Alice"),
            ],
            "bureau": [
                GroupEntry(user_id="U0000003", comment="Martin"),
            ],
        },
        notifications=NotificationConfig(
            reply_in_thread=True,
            deduplicate=True,
            exclude_author=True,
            state_database="/tmp/test_group_bot.sqlite3",
            message_template="cc {mentions}",
        ),
        retention=RetentionConfig(dedup_days=90),
    )


@pytest.fixture
def store(tmp_path):
    s = DedupStore(tmp_path / "test.sqlite3")
    yield s
    s.close()


@pytest.fixture
def module(config, store, mock_slack):
    return GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)


@pytest.fixture
def mock_app():
    app = MagicMock()
    handlers = {}

    def capture_event(event_type):
        def decorator(func):
            handlers[event_type] = func
            return func
        return decorator

    app.event = capture_event
    app._handlers = handlers
    return app


class TestGroupsModuleRegistration:
    def test_register_attaches_message_handler(self, module, mock_app):
        module.register(mock_app)
        assert "message" in mock_app._handlers

    def test_module_name(self, module):
        assert module.name == "groups"


class TestGroupsModuleMessageHandling:
    def test_basic_notification(self, module, mock_app, mock_slack, store):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "Bonjour la team @com j'ai ce visuel",
        }
        handler(event, MagicMock(), MagicMock())

        mock_slack.post_message.assert_called_once()
        call_kwargs = mock_slack.post_message.call_args.kwargs
        assert call_kwargs["channel"] == "C0001"
        assert call_kwargs["thread_ts"] == "1700000.000100"
        assert "<@U0000001>" in call_kwargs["text"]
        assert "<@U0000002>" in call_kwargs["text"]
        assert call_kwargs["text"] == "cc <@U0000001> <@U0000002>"

    def test_bot_message_ignored(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "subtype": "bot_message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "text": "@com bonjour",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_no_alias_no_notification(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "Bonjour la team",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_author_excluded(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U0000001",  # author is in com group
            "text": "@com bonjour",
        }
        handler(event, MagicMock(), MagicMock())

        call_text = mock_slack.post_message.call_args.kwargs["text"]
        assert "<@U0000001>" not in call_text
        assert "<@U0000002>" in call_text

    def test_thread_reply_uses_thread_ts(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000200",
            "thread_ts": "1700000.000100",
            "user": "U9999",
            "text": "@com voir le fil",
        }
        handler(event, MagicMock(), MagicMock())

        call_kwargs = mock_slack.post_message.call_args.kwargs
        assert call_kwargs["thread_ts"] == "1700000.000100"

    def test_redelivery_no_duplicate(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com bonjour",
        }

        handler(event, MagicMock(), MagicMock())
        mock_slack.reset_mock()
        handler(event, MagicMock(), MagicMock())

        mock_slack.post_message.assert_not_called()

    def test_ici_does_not_trigger(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@ici attention tous",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_here_does_not_trigger(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@here regardez ça",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_channel_whitelist(self, config, store, mock_slack, mock_app):
        config = dataclasses.replace(
            config,
            filters=dataclasses.replace(config.filters, allowed_channel_ids=["C_ALLOWED"]),
        )
        module = GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event_disallowed = {
            "type": "message",
            "channel": "C_OTHER",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com bonjour",
        }
        handler(event_disallowed, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

        event_allowed = {
            "type": "message",
            "channel": "C_ALLOWED",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com bonjour",
        }
        handler(event_allowed, MagicMock(), MagicMock())
        mock_slack.post_message.assert_called_once()

    def test_channel_blacklist(self, config, store, mock_slack, mock_app):
        config = dataclasses.replace(
            config,
            filters=dataclasses.replace(config.filters, ignored_channel_ids=["C_IGNORED"]),
        )
        module = GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C_IGNORED",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com bonjour",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_multiple_aliases_in_message(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com @bureau réunion",
        }
        handler(event, MagicMock(), MagicMock())

        call_text = mock_slack.post_message.call_args.kwargs["text"]
        assert "<@U0000001>" in call_text
        assert "<@U0000002>" in call_text
        assert "<@U0000003>" in call_text

    def test_message_deleted_ignored(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "subtype": "message_deleted",
            "channel": "C0001",
            "ts": "1700000.000100",
            "text": "@com",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_empty_text_ignored(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_thread_replies_ignored_when_configured(self, config, store, mock_slack, mock_app):
        config = dataclasses.replace(
            config,
            filters=dataclasses.replace(config.filters, ignore_thread_replies=True),
        )
        module = GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000200",
            "thread_ts": "1700000.000100",
            "user": "U9999",
            "text": "@com en réponse",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()

    def test_root_message_still_processed_when_thread_replies_ignored(
        self, config, store, mock_slack, mock_app
    ):
        config = dataclasses.replace(
            config,
            filters=dataclasses.replace(config.filters, ignore_thread_replies=True),
        )
        module = GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com bonjour",
        }
        handler(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_called_once()

    def test_persistence_across_module_recreation(self, config, store, mock_slack, mock_app):
        module1 = GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)
        module1.register(mock_app)
        handler1 = mock_app._handlers["message"]

        event = {
            "type": "message",
            "channel": "C0001",
            "ts": "1700000.000100",
            "user": "U9999",
            "text": "@com bonjour",
        }
        handler1(event, MagicMock(), MagicMock())

        mock_slack.reset_mock()

        module2 = GroupsModule(config=config, dedup_store=store, slack_client=mock_slack)
        module2.register(mock_app)
        handler2 = mock_app._handlers["message"]

        handler2(event, MagicMock(), MagicMock())
        mock_slack.post_message.assert_not_called()
