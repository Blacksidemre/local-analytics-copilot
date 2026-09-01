from __future__ import annotations

import os

import uvicorn


def desktop_port(raw: str | None = None) -> int:
    value = raw if raw is not None else os.getenv("LAC_BRIDGE_PORT", "8765")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("LAC_BRIDGE_PORT geçerli bir port olmalı") from exc
    if not 1024 <= port <= 65535:
        raise ValueError("LAC_BRIDGE_PORT 1024-65535 arasında olmalı")
    return port


def main() -> None:
    uvicorn.run(
        "lacopilot.app:app",
        host="127.0.0.1",
        port=desktop_port(),
        log_level=os.getenv("LAC_LOG_LEVEL", "info"),
        access_log=False,
    )


if __name__ == "__main__":  # pragma: no cover - packaged entry point
    main()
