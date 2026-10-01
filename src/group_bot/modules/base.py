"""Base module interface for group_bot's modular architecture.

Each module inherits BaseModule and registers Slack event handlers
in its register() method. New features can be added as new modules
without modifying existing code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slack_bolt import App


class BaseModule:
    """Base class for all group_bot modules.

    Subclasses must implement register() to attach event handlers
    to the Slack Bolt app.
    """

    name: str = "base"

    def register(self, app: App) -> None:
        """Register Slack event handlers on the Bolt app.

        Args:
            app: The slack_bolt.App instance.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement register()")
