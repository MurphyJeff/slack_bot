"""Thread notifier: composes and posts notifications in Slack threads.

Composes the notification text from the configured template, generates
individual Slack mention links (<@U...>), and posts the message in
the original message's thread using the Slack API.

Thread behavior:
- If the original message has a thread_ts, reply in that thread
- If the original message is a root message (no thread_ts), use its ts
  to start a new thread
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from group_bot.logger import truncate_id, truncate_ts
from group_bot.modules.groups.dedup import DedupStore

log = structlog.get_logger("group_bot.notifier")


@dataclass(frozen=True)
class NotificationResult:
    """Result of a notification attempt.

    Attributes:
        posted: Whether the notification was successfully posted to Slack.
        notified_user_ids: User IDs that were mentioned in the notification.
        skipped_user_ids: User IDs that were already notified (dedup hit).
        thread_ts: The thread_ts used for the notification.
        error: Error message if posting failed, None otherwise.
    """

    posted: bool
    notified_user_ids: list[str]
    skipped_user_ids: list[str]
    thread_ts: str
    error: str | None = None


def format_mentions(user_ids: list[str]) -> str:
    """Format user IDs as Slack mention links.

    Args:
        user_ids: List of Slack user IDs.

    Returns:
        Space-separated mention links, e.g. "<@U0001> <@U0002>".
    """
    return " ".join(f"<@{uid}>" for uid in user_ids)


def compose_message(template: str, user_ids: list[str]) -> str:
    """Compose the notification message from the template.

    Args:
        template: Message template containing {mentions} placeholder.
        user_ids: List of Slack user IDs to mention.

    Returns:
        Formatted message text with mentions.
    """
    mentions = format_mentions(user_ids)
    return template.replace("{mentions}", mentions)


def resolve_thread_ts(event: dict) -> str:
    """Determine the thread_ts for the notification reply.

    If the message is already in a thread (has thread_ts), reply in
    that thread. Otherwise, use the message's own ts to start a thread.

    Args:
        event: Slack message event dict.

    Returns:
        The thread_ts to use for the reply.
    """
    thread_ts = event.get("thread_ts")
    if thread_ts:
        return thread_ts
    return event.get("ts", "")


class ThreadNotifier:
    """Composes and posts thread notifications with deduplication.

    Coordinates between the dedup store and the Slack client to ensure
    each user is notified at most once per message.
    """

    def __init__(
        self,
        dedup_store: DedupStore,
        message_template: str,
        slack_client=None,
    ):
        """Initialize the notifier.

        Args:
            dedup_store: DedupStore instance for persistence.
            message_template: Template string with {mentions} placeholder.
            slack_client: Slack client wrapper with post_message method.
        """
        self._dedup = dedup_store
        self._template = message_template
        self._slack = slack_client

    def notify(
        self,
        channel_id: str,
        message_ts: str,
        thread_ts: str,
        user_ids: list[str],
    ) -> NotificationResult:
        """Post a notification in the thread with dedup-checked mentions.

        Args:
            channel_id: Slack channel ID.
            message_ts: Timestamp of the original message (for dedup key).
            thread_ts: Thread timestamp to reply in.
            user_ids: User IDs to notify.

        Returns:
            NotificationResult with outcome details.
        """
        if not user_ids:
            log.info("no_users_to_notify", channel_id=truncate_id(channel_id))
            return NotificationResult(
                posted=False,
                notified_user_ids=[],
                skipped_user_ids=[],
                thread_ts=thread_ts,
            )

        to_notify: list[str] = []
        skipped: list[str] = []

        for uid in user_ids:
            if self._dedup.is_notified(channel_id, message_ts, uid):
                skipped.append(uid)
            else:
                to_notify.append(uid)

        if not to_notify:
            log.info(
                "all_users_already_notified",
                channel_id=truncate_id(channel_id),
                message_ts=truncate_ts(message_ts),
                skipped_count=len(skipped),
            )
            return NotificationResult(
                posted=False,
                notified_user_ids=[],
                skipped_user_ids=skipped,
                thread_ts=thread_ts,
            )

        text = compose_message(self._template, to_notify)

        try:
            self._slack.post_message(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts,
            )
        except Exception as e:
            log.error(
                "slack_post_failed",
                channel_id=truncate_id(channel_id),
                thread_ts=truncate_ts(thread_ts),
                error=str(e),
            )
            return NotificationResult(
                posted=False,
                notified_user_ids=[],
                skipped_user_ids=skipped,
                thread_ts=thread_ts,
                error=str(e),
            )

        self._dedup.mark_notified_batch(channel_id, message_ts, to_notify)

        log.info(
            "notification_posted",
            channel_id=truncate_id(channel_id),
            thread_ts=truncate_ts(thread_ts),
            notified_count=len(to_notify),
            skipped_count=len(skipped),
        )

        return NotificationResult(
            posted=True,
            notified_user_ids=to_notify,
            skipped_user_ids=skipped,
            thread_ts=thread_ts,
        )
