"""Groups module: registers Slack event handlers for alias notifications.

Wires together: alias detection → user resolution → dedup check →
thread notification. Filters bot messages, channel whitelist/blacklist,
and thread reply preferences.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from group_bot.config import AppConfig
from group_bot.logger import truncate_id, truncate_ts
from group_bot.modules.base import BaseModule
from group_bot.modules.groups.dedup import DedupStore
from group_bot.modules.groups.detector import AliasDetector
from group_bot.modules.groups.notifier import ThreadNotifier, resolve_thread_ts
from group_bot.modules.groups.resolver import UserResolver

if TYPE_CHECKING:
    from slack_bolt import App

log = structlog.get_logger("group_bot.groups")


class GroupsModule(BaseModule):
    """Module for group mention notifications (@com, @bureau, etc.).

    Detects configured aliases in messages, resolves them to user IDs,
    deduplicates, and posts notifications in the message's thread.
    """

    name = "groups"

    def __init__(
        self,
        config: AppConfig,
        dedup_store: DedupStore,
        slack_client=None,
    ):
        """Initialize the groups module.

        Args:
            config: Application configuration.
            dedup_store: DedupStore for notification persistence.
            slack_client: SlackClient for posting messages.
        """
        self._config = config
        self._dedup = dedup_store
        self._slack = slack_client

        aliases = list(config.groups.keys())
        self._detector = AliasDetector(aliases)
        self._resolver = UserResolver(config.groups)
        self._notifier = ThreadNotifier(
            dedup_store=dedup_store,
            message_template=config.notifications.message_template,
            slack_client=slack_client,
        )

    def _should_process(self, event: dict) -> bool:
        """Check if a message event should be processed.

        Args:
            event: Slack message event.

        Returns:
            True if the message should be processed.
        """
        msg_type = event.get("type", "")
        subtype = event.get("subtype")

        if subtype == "bot_message" and self._config.filters.ignore_bot_messages:
            return False

        if subtype in ("message_deleted", "channel_join", "channel_leave"):
            return False

        if subtype == "message_changed":
            changed = event.get("message", {})
            text = changed.get("text", "")
            event["text"] = text
            event["ts"] = changed.get("ts", event.get("ts", ""))
            event["thread_ts"] = changed.get("thread_ts") or event.get("thread_ts")
            event["user"] = changed.get("user", event.get("user"))

        if msg_type in ("message", "message_changed") and not subtype:
            pass

        if not event.get("text"):
            return False

        channel_id = event.get("channel", "")
        if not channel_id:
            return False

        allowed = self._config.filters.allowed_channel_ids
        if allowed and channel_id not in allowed:
            return False

        ignored = self._config.filters.ignored_channel_ids
        if channel_id in ignored:
            return False

        is_thread_reply = (
            event.get("thread_ts") is not None
            and event.get("thread_ts") != event.get("ts")
        )
        if self._config.filters.ignore_thread_replies and is_thread_reply:
            return False

        return True

    def register(self, app: App) -> None:
        """Register the message event handler on the Bolt app.

        Args:
            app: The slack_bolt.App instance.
        """

        @app.event("message")
        def handle_message(event, say, client):
            if not self._should_process(event):
                return

            text = event.get("text", "")
            channel_id = event.get("channel", "")
            message_ts = event.get("ts", "")
            user_id = event.get("user")

            aliases = self._detector.detect(text)
            if not aliases:
                return

            log.info(
                "aliases_detected",
                channel_id=truncate_id(channel_id),
                message_ts=truncate_ts(message_ts),
                aliases=aliases,
            )

            result = self._resolver.resolve(
                aliases=aliases,
                author_user_id=user_id,
                exclude_author=self._config.notifications.exclude_author,
            )

            if not result.user_ids:
                log.info(
                    "no_recipients_after_resolution",
                    channel_id=truncate_id(channel_id),
                    message_ts=truncate_ts(message_ts),
                )
                return

            thread_ts = resolve_thread_ts(event)

            self._notifier.notify(
                channel_id=channel_id,
                message_ts=message_ts,
                thread_ts=thread_ts,
                user_ids=result.user_ids,
            )
