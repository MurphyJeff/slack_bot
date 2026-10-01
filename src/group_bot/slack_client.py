"""Slack API client wrapper with rate limit handling and retries.

Wraps slack-sdk's WebClient to provide a clean interface for the
notifier module. Handles rate limits with exponential backoff and
retries transient failures.
"""

from __future__ import annotations

import time

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from group_bot.logger import redact_token, truncate_id, truncate_ts

log = structlog.get_logger("group_bot.slack_client")

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class SlackClient:
    """Wrapper around slack-sdk WebClient with retry logic.

    Provides a minimal interface for posting messages. Handles
    SlackApiError rate limits with exponential backoff.
    """

    def __init__(self, bot_token: str):
        """Initialize the Slack client.

        Args:
            bot_token: Slack Bot User OAuth Token (xoxb-...).
        """
        self._client = WebClient(token=bot_token)
        log.info("slack_client_initialized", token=redact_token(bot_token))

    def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict:
        """Post a message to a Slack channel, optionally in a thread.

        Retries on rate limit errors with exponential backoff.

        Args:
            channel: Channel ID to post to.
            text: Message text (may contain Slack mention links).
            thread_ts: Thread timestamp to reply in, or None for root message.

        Returns:
            Slack API response dict.

        Raises:
            SlackApiError: If the request fails after all retries.
        """
        last_error: Exception | None = None
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.chat_postMessage(
                    channel=channel,
                    text=text,
                    thread_ts=thread_ts if thread_ts else None,
                )
                log.info(
                    "message_posted",
                    channel=truncate_id(channel),
                    thread_ts=truncate_ts(thread_ts) if thread_ts else None,
                    ok=response.get("ok", False),
                )
                return response

            except SlackApiError as e:
                last_error = e
                if e.response and e.response.status_code == 429:
                    retry_after = float(
                        e.response.headers.get("Retry-After", backoff)
                    )
                    log.warning(
                        "rate_limited",
                        channel=truncate_id(channel),
                        retry_after=retry_after,
                        attempt=attempt + 1,
                    )
                    time.sleep(retry_after)
                    backoff *= 2
                    continue

                log.error(
                    "slack_api_error",
                    channel=truncate_id(channel),
                    error=str(e),
                    status_code=e.response.status_code if e.response else None,
                    attempt=attempt + 1,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise

            except Exception as e:
                last_error = e
                log.error(
                    "unexpected_error",
                    channel=truncate_id(channel),
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("post_message exhausted retries without error")
