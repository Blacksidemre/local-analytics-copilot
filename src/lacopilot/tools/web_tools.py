from __future__ import annotations

from lacopilot.config import get_settings
from lacopilot.security import validate_public_web_query


def public_web_search(query: str, max_results: int = 5) -> dict:
    """Optional public-web research. Disabled by default and blocks likely PII in queries.

    This tool is for public information only. Never include local data rows, debtor/customer identifiers,
    confidential company content, or secrets in the query.
    """
    s = get_settings()
    if not s.allow_web:
        raise PermissionError(
            "Web access disabled. Set LAC_ALLOW_WEB=true only after reviewing privacy policy."
        )
    safe = validate_public_web_query(query)
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise RuntimeError(
            "Web search için optional dependency kurun: pip install -e '.[web]'"
        ) from exc
    limit = max(1, min(int(max_results), 10))
    results = []
    for r in DDGS().text(safe, max_results=limit):
        results.append(
            {
                "title": r.get("title"),
                "url": r.get("href") or r.get("url"),
                "snippet": r.get("body"),
            }
        )
    return {
        "query": safe,
        "results": results,
        "privacy": "No local dataset content should be placed in public web queries.",
    }
