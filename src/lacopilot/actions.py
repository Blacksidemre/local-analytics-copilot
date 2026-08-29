from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ActionStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS actions(
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    risk_kind TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status, created_at DESC)"
            )

    @staticmethod
    def _canonical(tool_name: str, arguments: dict[str, Any]) -> tuple[str, str]:
        payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
        fingerprint = hashlib.sha256(f"{tool_name}\0{payload}".encode()).hexdigest()
        return payload, fingerprint

    def enqueue(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        risk_kind: str,
        reason: str,
    ) -> dict[str, Any]:
        payload, fingerprint = self._canonical(tool_name, arguments)
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM actions WHERE fingerprint=? AND status='pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
            if existing:
                return self._row(existing)
            action_id = uuid.uuid4().hex
            connection.execute(
                """INSERT INTO actions(
                    id,fingerprint,tool_name,arguments_json,risk_kind,reason,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,'pending',?,?)""",
                (action_id, fingerprint, tool_name, payload, risk_kind, reason, now, now),
            )
        return self.get(action_id)

    def get(self, action_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise KeyError(action_id)
        return self._row(row)

    def list(self, status: str | None = "pending", limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM actions"
        arguments: list[Any] = []
        if status:
            query += " WHERE status=?"
            arguments.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        arguments.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, arguments).fetchall()
        return [self._row(row) for row in rows]

    def reject(self, action_id: str) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE actions SET status='rejected',updated_at=? WHERE id=? AND status='pending'",
                (now, action_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Action bulunamadı veya pending durumda değil")
        return self.get(action_id)

    def approve_and_execute(
        self,
        action_id: str,
        executor: Callable[[str, dict[str, Any]], Any],
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row or row["status"] != "pending":
                raise ValueError("Action bulunamadı veya pending durumda değil")
            connection.execute(
                "UPDATE actions SET status='running',updated_at=? WHERE id=?",
                (now, action_id),
            )

        arguments = json.loads(row["arguments_json"])
        try:
            result = executor(row["tool_name"], arguments)
            result_json = json.dumps(result, ensure_ascii=False, default=str)
            if len(result_json) > 200000:
                result_json = result_json[:200000] + "\n...[stored result truncated]"
            status = "completed"
            error = None
        except Exception as exc:
            result_json = None
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"[:4000]

        with self._connect() as connection:
            connection.execute(
                "UPDATE actions SET status=?,result_json=?,error=?,updated_at=? WHERE id=?",
                (status, result_json, error, datetime.now(UTC).isoformat(), action_id),
            )
        return self.get(action_id)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["arguments"] = json.loads(data.pop("arguments_json"))
        raw_result = data.pop("result_json")
        if raw_result:
            try:
                data["result"] = json.loads(raw_result)
            except json.JSONDecodeError:
                data["result"] = raw_result
        else:
            data["result"] = None
        data.pop("fingerprint", None)
        return data
