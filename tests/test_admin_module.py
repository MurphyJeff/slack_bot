"""Tests for the admin module slash commands."""

import dataclasses
from unittest.mock import MagicMock

import pytest

from group_bot.config import (
    AdminCommandsConfig,
    AppConfig,
    FilterConfig,
    GroupEntry,
    NotificationConfig,
    RetentionConfig,
    SlackConfig,
)
from group_bot.modules.admin.module import AdminModule


@pytest.fixture
def mock_slack():
    client = MagicMock()
    client.get_user_info.return_value = None
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
        admin_commands=AdminCommandsConfig(enabled=True),
    )


@pytest.fixture
def module(config, mock_slack):
    return AdminModule(config=config, slack_client=mock_slack)


@pytest.fixture
def mock_app():
    app = MagicMock()
    handlers = {}

    def capture_command(cmd):
        def decorator(func):
            handlers[cmd] = func
            return func
        return decorator

    app.command = capture_command
    app._handlers = handlers
    return app


class TestAdminModuleRegistration:
    def test_register_attaches_group_list_handler(self, module, mock_app):
        module.register(mock_app)
        assert "/group-list" in mock_app._handlers

    def test_register_attaches_help_handler(self, module, mock_app):
        module.register(mock_app)
        assert "/help" in mock_app._handlers

    def test_module_name(self, module):
        assert module.name == "admin"


class TestGroupListCommand:
    def test_basic_response(self, module, mock_app, mock_slack):
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        mock_ack = MagicMock()
        mock_respond = MagicMock()
        handler(mock_ack, {"user_id": "U9999"}, mock_respond)

        mock_ack.assert_called_once()
        mock_respond.assert_called_once()
        text = mock_respond.call_args.args[0]
        assert "Groupes configurés:" in text
        assert "com" in text
        assert "bureau" in text

    def test_uses_slack_display_name(self, module, mock_app, mock_slack):
        mock_slack.get_user_info.return_value = {
            "real_name": "Julie Maillard",
            "display_name": "julie",
        }
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        handler(MagicMock(), {"user_id": "U9999"}, MagicMock())

        assert mock_slack.get_user_info.call_count == 3
        for call_args in mock_slack.get_user_info.call_args_list:
            assert call_args.args[0].startswith("U")

    def test_falls_back_to_comment_when_api_fails(self, module, mock_app, mock_slack):
        mock_slack.get_user_info.return_value = None
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "Martine" in text
        assert "Alice" in text
        assert "Martin" in text

    def test_falls_back_to_truncated_id_without_comment(self, config, mock_app, mock_slack):
        config = dataclasses.replace(
            config,
            groups={
                "com": [GroupEntry(user_id="U12345678", comment="")],
            },
        )
        module = AdminModule(config=config, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "U123" in text

    def test_member_count_in_response(self, module, mock_app, mock_slack):
        mock_slack.get_user_info.return_value = None
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "(2)" in text
        assert "(1)" in text

    def test_caches_user_info(self, config, mock_app, mock_slack):
        mock_slack.get_user_info.return_value = {"real_name": "Test User"}
        config = dataclasses.replace(
            config,
            groups={
                "com": [
                    GroupEntry(user_id="U0000001", comment=""),
                    GroupEntry(user_id="U0000001", comment=""),
                ],
            },
        )
        module = AdminModule(config=config, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        handler(MagicMock(), {"user_id": "U9999"}, MagicMock())

        assert mock_slack.get_user_info.call_count == 2

    def test_empty_groups_message(self, config, mock_app, mock_slack):
        config = dataclasses.replace(config, groups={})
        module = AdminModule(config=config, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["/group-list"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "Aucun groupe configuré" in text


class TestHelpCommand:
    def test_basic_response(self, module, mock_app):
        module.register(mock_app)
        handler = mock_app._handlers["/help"]

        mock_ack = MagicMock()
        mock_respond = MagicMock()
        handler(mock_ack, {"user_id": "U9999"}, mock_respond)

        mock_ack.assert_called_once()
        mock_respond.assert_called_once()
        text = mock_respond.call_args.args[0]
        assert "CAEP Bot" in text
        assert "/group-list" in text
        assert "/help" in text

    def test_lists_group_aliases(self, module, mock_app):
        module.register(mock_app)
        handler = mock_app._handlers["/help"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "@com" in text
        assert "@bureau" in text

    def test_no_aliases_message(self, config, mock_app, mock_slack):
        config = dataclasses.replace(config, groups={})
        module = AdminModule(config=config, slack_client=mock_slack)
        module.register(mock_app)
        handler = mock_app._handlers["/help"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "(aucun)" in text

    def test_mentions_native_mentions_excluded(self, module, mock_app):
        module.register(mock_app)
        handler = mock_app._handlers["/help"]

        mock_respond = MagicMock()
        handler(MagicMock(), {"user_id": "U9999"}, mock_respond)

        text = mock_respond.call_args.args[0]
        assert "@ici" in text
        assert "@here" in text
        assert "non gérées" in text
