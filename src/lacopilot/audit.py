from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lacopilot.security import redact_possible_pii

_lock = threading.Lock()


def _sanitize(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(
        token in lowered for token in ("password", "secret", "token", "api_key", "authorization")
    ):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_possible_pii(value[:4000])
    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value[:100]]
    return value


def audit(log_dir: Path, event: str, **payload: Any) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **_sanitize(payload),
    }
    path = log_dir / "audit.jsonl"
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
