# AGENTS.md

## Project: group_bot — CAEP Slack Bot

### Language & Runtime
- Python 3.11+
- Package manager: pip + pyproject.toml
- Key dependencies: slack-bolt, slack-sdk, pyyaml, structlog

### Commands
- **Install dev**: `pip install -e ".[dev]"`
- **Run locally**: `python -m group_bot --config config.yaml`
- **Run tests**: `pytest`
- **Lint**: `ruff check src/ tests/`
- **Type check**: (none configured yet)

### Architecture
- Modular: `src/group_bot/modules/` contains feature modules
- Each module inherits `BaseModule` and registers Slack event handlers
- Current module: `groups/` (alias detection → user resolution → dedup → thread notification)
- Config: YAML file + environment variables for secrets (never in code or config file)
- State: SQLite for deduplication persistence

### Security Rules
- NEVER commit `.env`, `config.yaml`, or `*.sqlite3` files
- NEVER log tokens, full message text, or full user IDs (truncate/anonymize)
- Tokens come ONLY from environment variables
- No Slack admin scopes — minimal permissions only
- Ignore bot messages to prevent loops

### Commit Conventions
- Format: `type: description` (feat, fix, docs, test, chore, refactor)
- Atomic commits: one feature/module per commit
- Tags: `vMAJOR.MINOR.PATCH` (semver), annotated

### Testing
- Unit tests in `tests/` mirror `src/` structure
- Use `pytest` + `pytest-mock` for mocking Slack API
- Test file naming: `test_<module>.py`
