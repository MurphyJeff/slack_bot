"""Admin module: slash commands for group listing and help.

Registers /group-list and /help slash command handlers.
/group-list fetches real Slack display names via users.info API.
/help displays available bot commands and features.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from group_bot.config import AppConfig
from group_bot.logger import truncate_id
from group_bot.modules.base import BaseModule
from group_bot.slack_client import SlackClient

if TYPE_CHECKING:
    from slack_bolt import App

log = structlog.get_logger("group_bot.admin")


class AdminModule(BaseModule):
    """Module for admin slash commands (/group-list, /help)."""

    name = "admin"

    def __init__(self, config: AppConfig, slack_client: SlackClient):
        """Initialize the admin module.

        Args:
            config: Application configuration.
            slack_client: SlackClient for users.info lookups.
        """
        self._config = config
        self._slack = slack_client

    def _get_display_name(self, user_id: str, fallback_comment: str) -> str:
        """Get a user's display name from Slack API, with fallback.

        Args:
            user_id: Slack user ID.
            fallback_comment: YAML comment to use if API fails.

        Returns:
            Display name from Slack, or comment, or truncated ID.
        """
        user_info = self._slack.get_user_info(user_id)
        if user_info:
            name = (
                user_info.get("real_name")
                or user_info.get("display_name")
                or user_info.get("name")
            )
            if name:
                return name

        if fallback_comment:
            return fallback_comment

        return truncate_id(user_id)

    def _build_group_list_text(self) -> str:
        """Build the /group-list response text.

        Returns:
            Formatted string listing all groups and their members.
        """
        lines = ["Groupes configurés:"]

        for alias, entries in self._config.groups.items():
            member_names = []
            for entry in entries:
                name = self._get_display_name(entry.user_id, entry.comment)
                member_names.append(name)

            count = len(member_names)
            members_str = ", ".join(member_names)
            lines.append(f"• {alias} ({count}): {members_str}")

        if self._config.groups:
            aliases_display = ", @".join(self._config.groups.keys())
            lines.append("")
            lines.append(
                f"Utilisez @{aliases_display} dans un message pour notifier les membres."
            )
        else:
            lines.append("Aucun groupe configuré.")

        return "\n".join(lines)

    def _build_help_text(self) -> str:
        """Build the /help response text.

        Returns:
            Formatted help string with available commands and features.
        """
        group_aliases = list(self._config.groups.keys())
        aliases_str = ", ".join(f"@{a}" for a in group_aliases) if group_aliases else "(aucun)"

        return (
            "CAEP Bot — Fonctions\n\n"
            "Commandes:\n"
            "  /group-list  — Lister les groupes configurés\n"
            "  /help        — Cette aide\n\n"
            "Mentions de groupe:\n"
            f"  {aliases_str} — Notifier les membres du groupe dans un fil\n\n"
            "Notes:\n"
            "  • La notification est postée dans le fil du message\n"
            "  • L'auteur du message n'est pas notifié\n"
            "  • @ici et @here sont des mentions natives Slack (non gérées par le bot)"
        )

    def register(self, app: App) -> None:
        """Register slash command handlers on the Bolt app.

        Args:
            app: The slack_bolt.App instance.
        """

        @app.command("/group-list")
        def handle_group_list(ack, command, respond):
            ack()
            log.info(
                "slash_command_received",
                command="/group-list",
                user_id=truncate_id(command.get("user_id", "")),
            )
            text = self._build_group_list_text()
            respond(text)

        @app.command("/help")
        def handle_help(ack, command, respond):
            ack()
            log.info(
                "slash_command_received",
                command="/help",
                user_id=truncate_id(command.get("user_id", "")),
            )
            text = self._build_help_text()
            respond(text)
