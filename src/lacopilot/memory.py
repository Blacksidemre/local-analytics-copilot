from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class LocalMemory:
    """Small auditable memory store.

    Important business rules can be saved as `candidate` first and explicitly approved.
    The LLM never silently promotes a candidate rule to approved status.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'approved',
                source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(kind, key)
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS learning_progress (
                topic TEXT PRIMARY KEY,
                score REAL NOT NULL DEFAULT 0,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                updated_at TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                outcome TEXT NOT NULL,
                reusable INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )""")

    def upsert(
        self, kind: str, key: str, value: str, status: str = "approved", source: str = "user"
    ) -> None:
        if status not in {"candidate", "approved", "rejected"}:
            raise ValueError("status candidate/approved/rejected olmalı")
        now = datetime.now(UTC).isoformat()
        with self._connect() as con:
            con.execute(
                """INSERT INTO memory(kind,key,value,status,source,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(kind,key) DO UPDATE SET
                  value=excluded.value,status=excluded.status,source=excluded.source,updated_at=excluded.updated_at
            """,
                (kind, key, value, status, source, now, now),
            )

    def list(self, kind: str | None = None, status: str | None = "approved") -> list[dict]:
        q = "SELECT * FROM memory WHERE 1=1"
        args = []
        if kind:
            q += " AND kind=?"
            args.append(kind)
        if status:
            q += " AND status=?"
            args.append(status)
        q += " ORDER BY id DESC"
        with self._connect() as con:
            rows = con.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    def approve(self, memory_id: int) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as con:
            cur = con.execute(
                "UPDATE memory SET status='approved',updated_at=? WHERE id=?", (now, memory_id)
            )
            if cur.rowcount == 0:
                raise KeyError(memory_id)

    def reject(self, memory_id: int) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as con:
            cur = con.execute(
                "UPDATE memory SET status='rejected',updated_at=? WHERE id=?", (now, memory_id)
            )
            if cur.rowcount == 0:
                raise KeyError(memory_id)

    def approved_context(self, limit: int = 30) -> str:
        rows = self.list(status="approved")[:limit]
        return "\n".join(f"[{r['kind']}] {r['key']}: {r['value']}" for r in rows)

    def update_learning(self, topic: str, delta: float, note: str = "") -> dict:
        now = datetime.now(UTC).isoformat()
        with self._connect() as con:
            row = con.execute("SELECT * FROM learning_progress WHERE topic=?", (topic,)).fetchone()
            old = float(row["score"]) if row else 0.0
            cnt = int(row["evidence_count"]) if row else 0
            score = max(0.0, min(100.0, old + delta))
            con.execute(
                """INSERT INTO learning_progress(topic,score,evidence_count,notes,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(topic) DO UPDATE SET
                score=excluded.score,evidence_count=excluded.evidence_count,notes=excluded.notes,updated_at=excluded.updated_at
            """,
                (topic, score, cnt + 1, note, now),
            )
        return {"topic": topic, "score": score, "evidence_count": cnt + 1}

    def learning_profile(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM learning_progress ORDER BY score DESC, topic"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_experience(
        self,
        task_type: str,
        summary: str,
        outcome: str,
        reusable: bool = False,
        metadata: dict | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO experiences(task_type,summary,outcome,reusable,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
                (
                    task_type,
                    summary,
                    outcome,
                    int(reusable),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )

    def reusable_workflow_suggestions(self, min_count: int = 3) -> list[dict]:
        """Detect repeated tool sequences from local agent experiences."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT metadata_json,summary,outcome,created_at FROM experiences WHERE reusable=1 ORDER BY id DESC LIMIT 1000"
            ).fetchall()
        groups = {}
        for r in rows:
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except Exception:
                continue
            tools = tuple(meta.get("tools") or [])
            if not tools:
                continue
            key = " -> ".join(tools)
            g = groups.setdefault(
                key,
                {
                    "tool_sequence": list(tools),
                    "count": 0,
                    "latest": r["created_at"],
                    "examples": [],
                },
            )
            g["count"] += 1
            if len(g["examples"]) < 3:
                g["examples"].append(r["summary"])
        return sorted(
            [v for v in groups.values() if v["count"] >= min_count],
            key=lambda x: x["count"],
            reverse=True,
        )
