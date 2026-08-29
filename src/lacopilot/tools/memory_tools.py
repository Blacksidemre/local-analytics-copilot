from __future__ import annotations

from lacopilot.config import get_settings
from lacopilot.memory import LocalMemory


def memory_propose(kind: str, key: str, value: str, source: str = "assistant_proposal") -> dict:
    """Save a candidate memory/business rule. The agent cannot approve it itself."""
    mem = LocalMemory(get_settings().memory_db)
    mem.upsert(kind=kind, key=key, value=value, status="candidate", source=source)
    return {
        "saved": True,
        "status": "candidate",
        "kind": kind,
        "key": key,
        "approval_required": True,
        "note": "Only the user/UI/CLI should promote candidate business rules to approved.",
    }


def memory_list(kind: str = "", status: str = "approved") -> dict:
    mem = LocalMemory(get_settings().memory_db)
    return {"items": mem.list(kind=kind or None, status=status or None)}


def workflow_suggestions(min_count: int = 3) -> dict:
    """Show repeated local tool sequences that may be worth turning into a reusable workflow. Does not create code automatically."""
    mem = LocalMemory(get_settings().memory_db)
    return {
        "suggestions": mem.reusable_workflow_suggestions(max(2, min(int(min_count), 20))),
        "rule": "A repeated sequence is only a candidate. Human review and regression tests are required before promotion.",
    }
