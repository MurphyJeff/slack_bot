"""Tests for configuration loading and validation."""


import pytest

from group_bot.config import (
    AppConfig,
    ConfigError,
    load_config,
)


@pytest.fixture
def _set_env_vars(monkeypatch):
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-1-test123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test456")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "signing-secret-789")


@pytest.fixture
def valid_config_yaml(tmp_path):
    content = """
slack:
  mode: socket
  app_token_env: SLACK_APP_TOKEN
  bot_token_env: SLACK_BOT_TOKEN
  signing_secret_env: SLACK_SIGNING_SECRET

filters:
  allowed_channel_ids: []
  ignored_channel_ids: []
  ignore_bot_messages: true
  ignore_thread_replies: false

groups:
  com:
    - user_id: "U0C5QA76"
      comment: "Martine"
  bureau:
    - user_id: "U0C5QAEE"
      comment: "Martin"
    - user_id: "U0ABCD99"
      comment: "Alice"

notifications:
  reply_in_thread: true
  deduplicate: true
  exclude_author: true
  state_database: "/tmp/test_state.sqlite3"
  message_template: "cc {mentions}"

retention:
  dedup_days: 30
"""
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


class TestLoadConfig:
    def test_load_valid_config(self, valid_config_yaml, _set_env_vars):
        config = load_config(valid_config_yaml)
        assert isinstance(config, AppConfig)
        assert config.slack.mode == "socket"
        assert config.slack.app_token == "xapp-1-test123"
        assert config.slack.bot_token == "xoxb-test456"
        assert config.slack.signing_secret == "signing-secret-789"

    def test_filters_defaults(self, valid_config_yaml, _set_env_vars):
        config = load_config(valid_config_yaml)
        assert config.filters.ignore_bot_messages is True
        assert config.filters.ignore_thread_replies is False
        assert config.filters.allowed_channel_ids == []

    def test_groups_parsed(self, valid_config_yaml, _set_env_vars):
        config = load_config(valid_config_yaml)
        assert "com" in config.groups
        assert "bureau" in config.groups
        assert config.groups["com"][0].user_id == "U0C5QA76"
        assert config.groups["com"][0].comment == "Martine"
        assert len(config.groups["bureau"]) == 2

    def test_notifications_template(self, valid_config_yaml, _set_env_vars):
        config = load_config(valid_config_yaml)
        assert config.notifications.message_template == "cc {mentions}"
        assert config.notifications.exclude_author is True

    def test_retention_parsed(self, valid_config_yaml, _set_env_vars):
        config = load_config(valid_config_yaml)
        assert config.retention.dedup_days == 30


class TestConfigErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_missing_env_var(self, valid_config_yaml, monkeypatch):
        monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
        with pytest.raises(ConfigError, match="SLACK_APP_TOKEN"):
            load_config(valid_config_yaml)

    def test_empty_env_var(self, valid_config_yaml, monkeypatch):
        monkeypatch.setenv("SLACK_APP_TOKEN", "  ")
        with pytest.raises(ConfigError, match="SLACK_APP_TOKEN"):
            load_config(valid_config_yaml)

    def test_invalid_mode(self, tmp_path, _set_env_vars):
        path = tmp_path / "config.yaml"
        path.write_text("slack:\n  mode: ftp\n")
        with pytest.raises(ConfigError, match="must be 'socket' or 'http'"):
            load_config(path)

    def test_invalid_user_id_format(self, tmp_path, _set_env_vars):
        path = tmp_path / "config.yaml"
        path.write_text(
            "slack:\n  mode: socket\n"
            "groups:\n  com:\n    - user_id: 'martine'\n"
        )
        with pytest.raises(ConfigError, match="does not look like a valid Slack user ID"):
            load_config(path)

    def test_missing_mentions_placeholder(self, tmp_path, _set_env_vars):
        path = tmp_path / "config.yaml"
        path.write_text(
            "slack:\n  mode: socket\n"
            "notifications:\n  message_template: 'hello world'\n"
        )
        with pytest.raises(ConfigError, match="must contain.*mentions"):
            load_config(path)

    def test_missing_user_id_in_group(self, tmp_path, _set_env_vars):
        path = tmp_path / "config.yaml"
        path.write_text(
            "slack:\n  mode: socket\n"
            "groups:\n  com:\n    - comment: 'no id'\n"
        )
        with pytest.raises(ConfigError, match="missing 'user_id'"):
            load_config(path)

    def test_dedup_days_too_small(self, tmp_path, _set_env_vars):
        path = tmp_path / "config.yaml"
        path.write_text(
            "slack:\n  mode: socket\n"
            "retention:\n  dedup_days: 0\n"
        )
        with pytest.raises(ConfigError, match="dedup_days must be >= 1"):
            load_config(path)

    def test_empty_groups_allowed(self, tmp_path, _set_env_vars):
        path = tmp_path / "config.yaml"
        path.write_text("slack:\n  mode: socket\n")
        config = load_config(path)
        assert config.groups == {}
