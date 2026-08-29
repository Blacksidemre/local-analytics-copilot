from __future__ import annotations

from lacopilot.security import validate_read_only_sql


def validate_sql_read_only(sql: str) -> dict:
    """Validate that a SQL statement is read-only before execution.

    Args:
        sql: SQL statement to validate.
    """
    safe = validate_read_only_sql(sql)
    return {
        "safe": True,
        "sql": safe,
        "note": "This validator is defense-in-depth; database execution still requires a technically read-only account.",
    }
