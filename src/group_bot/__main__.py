"""Entry point for group_bot: python -m group_bot --config config.yaml"""

from __future__ import annotations

import argparse
import sys

from group_bot.config import ConfigError, load_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CAEP Group Bot — Slack group mention notifications"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    from group_bot.app import run

    run(config)


if __name__ == "__main__":
    main()
