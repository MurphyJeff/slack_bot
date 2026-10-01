# CAEP Group Bot

Slack bot for the CAEP association. Detects custom group mentions
(`@com`, `@bureau`) in messages and notifies group members in the
message's thread with individual Slack mentions.

## Features

- **Custom group mentions**: configure aliases like `@com`, `@bureau`
  with multiple Slack users each, editable via YAML — no code changes
- **Thread notifications**: posts `cc <@U...> <@U...>` in the original
  message's thread
- **Deduplication**: each user is notified at most once per message,
  persisted in SQLite — survives restarts and Slack event redelivery
- **Author exclusion**: the message author is never pinged
- **Native mention exclusion**: `@ici`, `@here`, `@channel`, `@everyone`
  never trigger the bot
- **Socket Mode**: no public HTTP endpoint needed
- **Modular architecture**: add new features as modules without touching
  existing code
- **Hardened systemd service**: dedicated nologin user, filesystem
  protections, journal logging

## Quick start (development)

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure secrets
cp .env.example .env
# Edit .env with your Slack tokens (see docs/SLACK_SETUP.md)

# 3. Configure groups
cp config.example.yaml config.yaml
# Edit config.yaml with your real Slack user IDs

# 4. Run
python -m group_bot --config config.yaml
```

## Project structure

```
src/group_bot/
├── __main__.py         # CLI entry point
├── app.py              # Slack Bolt orchestration (Socket Mode)
├── config.py           # YAML config + env secrets + validation
├── logger.py           # Structured logging (no secrets in logs)
├── slack_client.py     # Slack API wrapper (rate limits, retries)
└── modules/
    ├── base.py         # BaseModule interface
    └── groups/
        ├── module.py    # Wiring: detect → resolve → dedup → notify
        ├── detector.py  # @com, @bureau regex detection
        ├── resolver.py  # Alias → user IDs, dedup, author exclusion
        ├── dedup.py     # SQLite persistent deduplication
        └── notifier.py  # Thread notification composition + posting
```

## Testing

```bash
python -m pytest          # 105 tests
ruff check src/ tests/    # Lint
```

## Documentation

- [Slack App Setup](docs/SLACK_SETUP.md) — create app, scopes, events
- [Deployment on Debian 12](docs/DEPLOYMENT.md) — systemd, install script
- [Operations](docs/OPERATIONS.md) — token rotation, logs, troubleshooting

## Configuration

See `config.example.yaml` for all options. Key sections:

```yaml
groups:
  com:
    - user_id: "U0C5QA76"  # Martine
    - user_id: "U0XXXXXX"  # Another member
  bureau:
    - user_id: "U0C5QAEE"  # Martin

notifications:
  message_template: "cc {mentions}"
  exclude_author: true
  deduplicate: true
```

## Security

- Tokens only from environment variables — never in config files or Git
- `.gitignore` excludes `.env`, `config.yaml`, `*.sqlite3`
- Logs truncate/anonymize user IDs, timestamps, and tokens
- Systemd hardening: `NoNewPrivileges`, `ProtectSystem=strict`,
  `CapabilityBoundingSet=` (empty), dedicated `groupbot` user
- No Slack admin scopes — minimal permissions only
- Bot messages ignored to prevent loops

## License

MIT
