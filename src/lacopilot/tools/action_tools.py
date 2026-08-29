from __future__ import annotations

from lacopilot.actions import ActionStore
from lacopilot.config import get_settings


def action_status(action_id: str) -> dict:
    """Read the status/result of a human-reviewed pending action by its action ID."""
    return ActionStore(get_settings().actions_db).get(action_id)
