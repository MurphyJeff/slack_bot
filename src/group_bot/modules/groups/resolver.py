"""User resolver: maps detected aliases to Slack user IDs.

Resolves aliases to concrete user IDs from configuration, deduplicates
across aliases (same person in multiple groups), and optionally excludes
the message author. Logs warnings for empty groups or invalid entries
without failing the entire processing.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from group_bot.config import GroupEntry
from group_bot.logger import truncate_id

log = structlog.get_logger("group_bot.resolver")


@dataclass(frozen=True)
class ResolutionResult:
    """Result of resolving aliases to user IDs.

    Attributes:
        user_ids: Ordered list of unique user IDs to notify.
        skipped_author: True if the author was excluded from results.
        empty_aliases: Aliases that had no configured users.
    """

    user_ids: list[str]
    skipped_author: bool
    empty_aliases: list[str]


class UserResolver:
    """Resolves detected aliases to Slack user IDs.

    Handles:
    - Multiple users per alias
    - Same user in multiple aliases (deduplication)
    - Exclusion of the message author
    - Empty aliases (logged as warnings)
    """

    def __init__(self, groups: dict[str, list[GroupEntry]]):
        """Initialize the resolver with group configuration.

        Args:
            groups: Mapping of alias name to list of GroupEntry objects.
        """
        self._groups = groups

    def resolve(
        self,
        aliases: list[str],
        author_user_id: str | None = None,
        exclude_author: bool = True,
    ) -> ResolutionResult:
        """Resolve aliases to a deduplicated list of user IDs.

        Args:
            aliases: List of alias names detected in the message.
            author_user_id: Slack user ID of the message author, if available.
            exclude_author: Whether to exclude the author from notifications.

        Returns:
            ResolutionResult with unique user IDs to notify.
        """
        resolved: list[str] = []
        seen: set[str] = set()
        empty_aliases: list[str] = []
        skipped_author = False

        for alias in aliases:
            entries = self._groups.get(alias, [])
            if not entries:
                empty_aliases.append(alias)
                log.warning(
                    "alias_has_no_users",
                    alias=alias,
                )
                continue

            for entry in entries:
                uid = entry.user_id
                if uid in seen:
                    continue

                if exclude_author and author_user_id and uid == author_user_id:
                    seen.add(uid)
                    skipped_author = True
                    log.info(
                        "excluding_author_from_notification",
                        alias=alias,
                        user_id=truncate_id(uid),
                    )
                    continue

                seen.add(uid)
                resolved.append(uid)

        log.info(
            "resolved_aliases",
            alias_count=len(aliases),
            user_count=len(resolved),
            empty_aliases=empty_aliases,
            skipped_author=skipped_author,
        )

        return ResolutionResult(
            user_ids=resolved,
            skipped_author=skipped_author,
            empty_aliases=empty_aliases,
        )
