"""Alias detection for custom group mentions (@com, @bureau).

Detects configured aliases as whole words in Slack message text.
Explicitly excludes Slack-native mentions (@ici, @here, @channel,
@everyone, @everyone) to avoid interference with native functionality.

Slack message text may contain:
- Plain text: "Bonjour @com" (our alias)
- Native mentions: "<@U12345>" (Slack user mention, not our concern)
- Native group mentions: "<!subteam^S123>" (Slack user group, not our concern)
- Native broadcasts: "<!here>", "<!channel>", "<!everyone>" (not our concern)

We only detect plain-text @alias patterns that match configured aliases.
"""

from __future__ import annotations

import re

# Slack-native mentions that must NEVER trigger our bot
NATIVE_MENTIONS = frozenset({
    "ici",
    "here",
    "channel",
    "everyone",
    "all",
    "group",
})


class AliasDetector:
    """Detects configured @aliases in Slack message text.

    Detects aliases as whole words (word boundary on both sides),
    case-insensitive. An alias like 'com' matches '@com', '@COM',
    '@Com!', '@com,' but NOT '@commerciale' or '@communication'.
    """

    def __init__(self, aliases: list[str]):
        """Initialize the detector with configured alias names.

        Args:
            aliases: List of alias names without the @ prefix (e.g. ['com', 'bureau']).
        """
        self._aliases = set(alias.lower() for alias in aliases)
        self._compiled_patterns: dict[str, re.Pattern[str]] = {}

        for alias in self._aliases:
            if alias in NATIVE_MENTIONS:
                raise ValueError(
                    f"Alias '{alias}' conflicts with a Slack-native mention. "
                    f"Native mentions {sorted(NATIVE_MENTIONS)} are excluded."
                )
            pattern = rf"@{re.escape(alias)}(?![a-z])"
            self._compiled_patterns[alias] = re.compile(pattern, re.IGNORECASE)

    @property
    def aliases(self) -> set[str]:
        """Return the set of configured alias names (lowercase)."""
        return set(self._aliases)

    def detect(self, text: str) -> list[str]:
        """Detect configured aliases in the given text.

        Args:
            text: The message text to scan (plain text, not Slack markup).

        Returns:
            List of detected alias names in lowercase, in order of first
            appearance. No duplicates.
        """
        if not text:
            return []

        detected: list[str] = []
        seen: set[str] = set()

        for alias in self._aliases:
            match = self._compiled_patterns[alias].search(text)
            if match and alias not in seen:
                detected.append((match.start(), alias))
                seen.add(alias)

        detected.sort(key=lambda item: item[0])
        return [alias for _, alias in detected]

    def is_native_mention(self, word: str) -> bool:
        """Check if a word is a Slack-native mention.

        Args:
            word: The word to check (without @ prefix).

        Returns:
            True if the word is a native Slack mention.
        """
        return word.lower() in NATIVE_MENTIONS
