"""Main application: orchestrates Slack Bolt Socket Mode, modules, and lifecycle.

Creates the Slack Bolt app, initializes all modules, and starts the
Socket Mode handler. Handles graceful shutdown.
"""

from __future__ import annotations

import signal
import sys

import structlog

from group_bot.config import AppConfig
from group_bot.logger import setup_logging
from group_bot.modules.admin.module import AdminModule
from group_bot.modules.base import BaseModule
from group_bot.modules.groups.dedup import DedupStore
from group_bot.modules.groups.module import GroupsModule
from group_bot.slack_client import SlackClient

log = structlog.get_logger("group_bot.app")


def create_modules(
    config: AppConfig, dedup: DedupStore, slack_client: SlackClient
) -> list[BaseModule]:
    """Create all enabled modules.

    Args:
        config: Application configuration.
        dedup: DedupStore instance.
        slack_client: SlackClient instance.

    Returns:
        List of BaseModule instances to register.
    """
    modules: list[BaseModule] = []

    if config.groups:
        modules.append(
            GroupsModule(
                config=config,
                dedup_store=dedup,
                slack_client=slack_client,
            )
        )

    if config.admin_commands.enabled:
        modules.append(
            AdminModule(
                config=config,
                slack_client=slack_client,
            )
        )

    return modules


def run(config: AppConfig) -> None:
    """Start the Slack bot in Socket Mode.

    Args:
        config: Validated application configuration.
    """
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    setup_logging()

    log.info(
        "starting_group_bot",
        mode=config.slack.mode,
        groups=list(config.groups.keys()),
    )

    app = App(
        token=config.slack.bot_token,
        signing_secret=config.slack.signing_secret,
    )

    dedup = DedupStore(config.notifications.state_database)
    slack_client = SlackClient(bot_token=config.slack.bot_token)

    modules = create_modules(config, dedup, slack_client)
    for module in modules:
        module.register(app)
        log.info("module_registered", module=module.name)

    cleaned = dedup.cleanup_old_records(config.retention.dedup_days)
    if cleaned > 0:
        log.info("startup_cleanup", records_removed=cleaned)

    def shutdown(signum, frame):
        log.info("shutdown_signal_received", signal=signum)
        dedup.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("socket_mode_starting")
    handler = SocketModeHandler(
        app_token=config.slack.app_token,
        app=app,
    )
    handler.start()
