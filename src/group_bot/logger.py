"""Structured logging configuration for group_bot.

Uses structlog for JSON-formatted logs. Never logs tokens, full message
text, or full user IDs — provides helper functions for anonymization.
"""

from __future__ import annotations

import logging

import structlog


def truncate_id(value: str, visible: int = 4) -> str:
    """Truncate an identifier for safe logging.

    Example: 'U0C5QA76' -> 'U0C5****'
    """
    if not value or len(value) <= visible:
        return "***"
    return value[:visible] + "*" * (len(value) - visible)


def truncate_ts(ts: str) -> str:
    """Truncate a Slack timestamp for safe logging.

    Example: '1700000000.000100' -> '1700000***'
    """
    if not ts:
        return "***"
    return ts[:7] + "***" if len(ts) > 7 else "***"


def redact_token(token: str) -> str:
    """Redact a token for safe logging.

    Example: 'xoxb-1234567890-abcdef' -> 'xoxb-1****'
    """
    if not token:
        return "***"
    prefix = token.split("-")[0] if "-" in token else token[:4]
    return f"{prefix}-****"


def setup_logging(level: str = "INFO") -> structlog.BoundLogger:
    """Configure structured logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).

    Returns:
        A bound logger instance.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
    )

    return structlog.get_logger("group_bot")
