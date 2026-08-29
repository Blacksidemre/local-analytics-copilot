from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class ConversationStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def _init(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id,id)"
            )

    def append(self, conversation_id: str, role: str, content: str, metadata: dict | None = None):
        with self._connect() as con:
            con.execute(
                "INSERT INTO messages(conversation_id,role,content,metadata_json,created_at) VALUES(?,?,?,?,?)",
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def history(self, conversation_id: str, limit: int = 30) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear(self, conversation_id: str):
        with self._connect() as con:
            con.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
