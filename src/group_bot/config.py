"""Configuration loading and validation for group_bot.

Loads YAML config, resolves secret references from environment variables,
and validates all required fields at startup. Fails fast on missing or
invalid configuration.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SLACK_USER_ID_RE = re.compile(r"^U[A-Z0-9]+$")


@dataclass(frozen=True)
class SlackConfig:
    mode: str
    app_token: str
    bot_token: str
    signing_secret: str


@dataclass(frozen=True)
class FilterConfig:
    allowed_channel_ids: list[str]
    ignored_channel_ids: list[str]
    ignore_bot_messages: bool
    ignore_thread_replies: bool


@dataclass(frozen=True)
class GroupEntry:
    user_id: str
    comment: str = ""


@dataclass(frozen=True)
class NotificationConfig:
    reply_in_thread: bool
    deduplicate: bool
    exclude_author: bool
    state_database: str
    message_template: str


@dataclass(frozen=True)
class RetentionConfig:
    dedup_days: int


@dataclass(frozen=True)
class AdminCommandsConfig:
    enabled: bool


@dataclass(frozen=True)
class AppConfig:
    slack: SlackConfig
    filters: FilterConfig
    groups: dict[str, list[GroupEntry]]
    notifications: NotificationConfig
    retention: RetentionConfig
    admin_commands: AdminCommandsConfig = field(
        default_factory=lambda: AdminCommandsConfig(enabled=True)
    )
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class ConfigError(Exception):
    """Raised when configuration is missing, invalid or incomplete."""


def load_config(path: str | Path) -> AppConfig:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigError: If the file is missing, malformed, or references
            environment variables that are not set.
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ConfigError("Config file must contain a top-level mapping")

    return _build_config(data)


def _resolve_env(env_key: str, context: str) -> str:
    """Resolve an environment variable reference.

    Args:
        env_key: Name of the environment variable.
        context: Human-readable context for error messages.

    Returns:
        The environment variable value.

    Raises:
        ConfigError: If the variable is not set or empty.
    """
    value = os.environ.get(env_key, "").strip()
    if not value:
        raise ConfigError(
            f"Environment variable '{env_key}' is not set or empty "
            f"(required by config key: {context})"
        )
    return value


def _build_slack_config(data: dict[str, Any]) -> SlackConfig:
    slack_data = data.get("slack", {})
    if not isinstance(slack_data, dict):
        raise ConfigError("'slack' section must be a mapping")

    mode = slack_data.get("mode", "socket")
    if mode not in ("socket", "http"):
        raise ConfigError(f"Invalid slack.mode '{mode}': must be 'socket' or 'http'")

    app_token = _resolve_env(
        slack_data.get("app_token_env", "SLACK_APP_TOKEN"), "slack.app_token_env"
    )
    bot_token = _resolve_env(
        slack_data.get("bot_token_env", "SLACK_BOT_TOKEN"), "slack.bot_token_env"
    )
    signing_secret = _resolve_env(
        slack_data.get("signing_secret_env", "SLACK_SIGNING_SECRET"),
        "slack.signing_secret_env",
    )

    return SlackConfig(
        mode=mode,
        app_token=app_token,
        bot_token=bot_token,
        signing_secret=signing_secret,
    )


def _build_filter_config(data: dict[str, Any]) -> FilterConfig:
    filters = data.get("filters", {})
    if not isinstance(filters, dict):
        raise ConfigError("'filters' section must be a mapping")

    return FilterConfig(
        allowed_channel_ids=list(filters.get("allowed_channel_ids", [])),
        ignored_channel_ids=list(filters.get("ignored_channel_ids", [])),
        ignore_bot_messages=bool(filters.get("ignore_bot_messages", True)),
        ignore_thread_replies=bool(filters.get("ignore_thread_replies", False)),
    )


def _build_groups(data: dict[str, Any]) -> dict[str, list[GroupEntry]]:
    groups_data = data.get("groups", {})
    if not isinstance(groups_data, dict):
        raise ConfigError("'groups' section must be a mapping")

    groups: dict[str, list[GroupEntry]] = {}
    for alias, entries in groups_data.items():
        if not isinstance(entries, list):
            raise ConfigError(f"groups.{alias} must be a list of user entries")

        parsed_entries: list[GroupEntry] = []
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ConfigError(f"groups.{alias}[{i}] must be a mapping with user_id")
            user_id = entry.get("user_id", "")
            if not user_id:
                raise ConfigError(f"groups.{alias}[{i}]: missing 'user_id'")
            if not SLACK_USER_ID_RE.match(user_id):
                raise ConfigError(
                    f"groups.{alias}[{i}]: user_id '{user_id}' does not look like "
                    f"a valid Slack user ID (expected format: U + uppercase alphanumeric)"
                )
            comment = entry.get("comment", "")
            parsed_entries.append(GroupEntry(user_id=user_id, comment=comment))

        groups[alias] = parsed_entries

    return groups


def _build_notification_config(data: dict[str, Any]) -> NotificationConfig:
    notif = data.get("notifications", {})
    if not isinstance(notif, dict):
        raise ConfigError("'notifications' section must be a mapping")

    template = notif.get("message_template", "cc {mentions}")
    if "{mentions}" not in template:
        raise ConfigError(
            "notifications.message_template must contain '{mentions}' placeholder"
        )

    return NotificationConfig(
        reply_in_thread=bool(notif.get("reply_in_thread", True)),
        deduplicate=bool(notif.get("deduplicate", True)),
        exclude_author=bool(notif.get("exclude_author", True)),
        state_database=notif.get("state_database", "/var/lib/group_bot/state.sqlite3"),
        message_template=template,
    )


def _build_retention_config(data: dict[str, Any]) -> RetentionConfig:
    retention = data.get("retention", {})
    if not isinstance(retention, dict):
        raise ConfigError("'retention' section must be a mapping")

    dedup_days = int(retention.get("dedup_days", 90))
    if dedup_days < 1:
        raise ConfigError("retention.dedup_days must be >= 1")

    return RetentionConfig(dedup_days=dedup_days)


def _build_admin_commands_config(data: dict[str, Any]) -> AdminCommandsConfig:
    admin_data = data.get("admin_commands", {})
    if not isinstance(admin_data, dict):
        raise ConfigError("'admin_commands' section must be a mapping")

    return AdminCommandsConfig(
        enabled=bool(admin_data.get("enabled", True)),
    )


def _build_config(data: dict[str, Any]) -> AppConfig:
    return AppConfig(
        slack=_build_slack_config(data),
        filters=_build_filter_config(data),
        groups=_build_groups(data),
        notifications=_build_notification_config(data),
        retention=_build_retention_config(data),
        admin_commands=_build_admin_commands_config(data),
        raw=data,
    )
