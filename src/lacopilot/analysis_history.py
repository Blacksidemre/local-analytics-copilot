from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|token|password|secret)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")
_FINDING_KEYS = {
    "finding_id",
    "kind",
    "label",
    "value",
    "unit",
    "source",
    "dimension",
    "warning",
}


def _redact_text(value: Any, *, limit: int) -> str:
    text = _CONTROL_CHARS.sub(" ", str(value)).strip()[:limit]
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return _BEARER_TOKEN.sub("Bearer [redacted]", text)


def _safe_dataset_ref(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not normalized:
        raise ValueError("dataset_ref workspace-relative olmalı")
    return normalized[:1000]


def _safe_finding(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - _FINDING_KEYS:
        raise ValueError("History yalnız typed finding sözleşmesini kabul eder")
    finding_id = value.get("finding_id")
    source = value.get("source")
    number = value.get("value")
    if not isinstance(finding_id, str) or not finding_id or len(finding_id) > 300:
        raise ValueError("History finding_id geçersiz")
    if not isinstance(source, str) or not source or len(source) > 300:
        raise ValueError("History finding source geçersiz")
    if (
        isinstance(number, bool)
        or not isinstance(number, (int, float))
        or not math.isfinite(float(number))
    ):
        raise ValueError("History yalnız finite deterministic numeric finding kabul eder")
    safe: dict[str, Any] = {
        "finding_id": finding_id,
        "value": number,
        "source": source,
    }
    for key, limit in (("kind", 100), ("label", 300), ("unit", 100), ("warning", 500)):
        item = value.get(key)
        if item is not None:
            safe[key] = _redact_text(item, limit=limit)
    dimension = value.get("dimension")
    if dimension is not None:
        if not isinstance(dimension, dict) or len(dimension) > 3:
            raise ValueError("History finding dimension geçersiz")
        safe["dimension"] = {
            _redact_text(key, limit=100): _redact_text(item, limit=200)
            for key, item in dimension.items()
            if isinstance(key, str) and isinstance(item, str)
        }
        if len(safe["dimension"]) != len(dimension):
            raise ValueError("History finding dimension yalnız metin kabul eder")
    return safe


def _comparison_contract(finding: dict[str, Any]) -> tuple[Any, ...]:
    dimension = finding.get("dimension")
    normalized_dimension = tuple(sorted(dimension.items())) if isinstance(dimension, dict) else None
    return (
        finding.get("kind"),
        finding.get("unit"),
        finding.get("source"),
        normalized_dimension,
    )


def _numeric_delta(baseline: int | float, current: int | float) -> int | float:
    if isinstance(baseline, int) and isinstance(current, int):
        return current - baseline
    delta = round(float(current) - float(baseline), 12)
    return 0.0 if delta == 0 else delta


def _relative_change_pct(baseline: int | float, delta: int | float) -> float | None:
    if float(baseline) == 0:
        return None
    result = round((float(delta) / abs(float(baseline))) * 100, 6)
    return 0.0 if result == 0 else result


class AnalysisHistoryStore:
    """Local, deletable archive of verified finding manifests.

    Raw rows, model prompts, tool arguments and secrets are intentionally not stored.
    Archived findings are never automatically promoted to current-run evidence.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    dataset_ref TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    question TEXT NOT NULL,
                    run_status TEXT NOT NULL,
                    verifier_status TEXT NOT NULL,
                    finding_count INTEGER NOT NULL,
                    findings_json TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_runs_created "
                "ON analysis_runs(created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_runs_dataset "
                "ON analysis_runs(dataset_id, created_at DESC)"
            )

    @staticmethod
    def _dataset_id(dataset_ref: str, source_path: Path) -> str:
        stat = source_path.stat()
        identity = f"{dataset_ref}\0{stat.st_size}\0{stat.st_mtime_ns}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def record_verified_agent_run(
        self,
        *,
        dataset_ref: str,
        source_path: Path,
        sheet_name: str,
        question: str,
        agent: dict[str, Any],
    ) -> str | None:
        run = agent.get("run")
        if not isinstance(run, dict):
            return None
        verification = run.get("verification")
        if not isinstance(verification, dict) or verification.get("status") != "passed":
            return None
        synthesis_request = run.get("synthesis_request")
        if not isinstance(synthesis_request, dict) or synthesis_request.get("status") != "ready":
            return None
        raw_findings = synthesis_request.get("evidence")
        if not isinstance(raw_findings, list) or not raw_findings or len(raw_findings) > 48:
            return None
        findings = [_safe_finding(finding) for finding in raw_findings]
        if len({finding["finding_id"] for finding in findings}) != len(findings):
            raise ValueError("History tekrar eden finding_id kabul etmez")

        plan = agent.get("plan")
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        tools = []
        for step in steps[:6]:
            tool = step.get("tool") if isinstance(step, dict) else None
            if isinstance(tool, str) and tool and tool not in tools:
                tools.append(tool[:100])

        normalized_ref = _safe_dataset_ref(dataset_ref)
        run_id = uuid.uuid4().hex
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO analysis_runs(
                    run_id,dataset_id,dataset_ref,source_name,sheet_name,mode,question,
                    run_status,verifier_status,finding_count,findings_json,tools_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    self._dataset_id(normalized_ref, source_path),
                    normalized_ref,
                    _redact_text(source_path.name, limit=300),
                    _redact_text(sheet_name, limit=200),
                    "agent",
                    _redact_text(question, limit=4000),
                    str(run.get("status", "completed"))[:40],
                    "passed",
                    len(findings),
                    json.dumps(findings, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(tools, ensure_ascii=False, separators=(",", ":")),
                    created_at,
                ),
            )
        return run_id

    def list_runs(self, *, limit: int = 50, dataset_id: str | None = None) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 100))
        query = """SELECT run_id,dataset_id,dataset_ref,source_name,sheet_name,mode,question,
                   run_status,verifier_status,finding_count,tools_json,created_at
                   FROM analysis_runs"""
        parameters: list[Any] = []
        if dataset_id is not None:
            query += " WHERE dataset_id=?"
            parameters.append(dataset_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(bounded_limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._decode_row(row, include_findings=False) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if not _RUN_ID.fullmatch(run_id):
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analysis_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return self._decode_row(row, include_findings=True) if row is not None else None

    def delete_run(self, run_id: str) -> bool:
        if not _RUN_ID.fullmatch(run_id):
            return False
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM analysis_runs WHERE run_id=?", (run_id,))
        return cursor.rowcount == 1

    def compare_runs(self, baseline_run_id: str, current_run_id: str) -> dict[str, Any]:
        """Compare two archived verifier-passed finding manifests without reopening data.

        The comparison is mechanical and evidence-only. It does not infer time-period meaning,
        business importance or causality, and it never promotes an archived finding into a new run.
        """

        if baseline_run_id == current_run_id:
            raise ValueError("Karşılaştırma için iki farklı analiz kaydı seçilmelidir")
        baseline = self.get_run(baseline_run_id)
        current = self.get_run(current_run_id)
        if baseline is None:
            raise KeyError(baseline_run_id)
        if current is None:
            raise KeyError(current_run_id)

        baseline_findings = self._verified_findings(baseline)
        current_findings = self._verified_findings(current)
        baseline_index = {finding["finding_id"]: finding for finding in baseline_findings}
        current_index = {finding["finding_id"]: finding for finding in current_findings}
        changes: list[dict[str, Any]] = []

        for finding_id in sorted(set(baseline_index) | set(current_index)):
            before = baseline_index.get(finding_id)
            after = current_index.get(finding_id)
            if before is None:
                changes.append(
                    {
                        "finding_id": finding_id,
                        "status": "added",
                        "label": after.get("label", finding_id),
                        "baseline_value": None,
                        "current_value": after["value"],
                        "absolute_delta": None,
                        "relative_change_pct": None,
                        "unit": after.get("unit"),
                        "source": after["source"],
                        "dimension": after.get("dimension"),
                    }
                )
                continue
            if after is None:
                changes.append(
                    {
                        "finding_id": finding_id,
                        "status": "removed",
                        "label": before.get("label", finding_id),
                        "baseline_value": before["value"],
                        "current_value": None,
                        "absolute_delta": None,
                        "relative_change_pct": None,
                        "unit": before.get("unit"),
                        "source": before["source"],
                        "dimension": before.get("dimension"),
                    }
                )
                continue
            if _comparison_contract(before) != _comparison_contract(after):
                incompatible_fields = [
                    field
                    for field in ("kind", "unit", "source", "dimension")
                    if before.get(field) != after.get(field)
                ]
                changes.append(
                    {
                        "finding_id": finding_id,
                        "status": "incompatible",
                        "label": after.get("label", before.get("label", finding_id)),
                        "baseline_value": before["value"],
                        "current_value": after["value"],
                        "absolute_delta": None,
                        "relative_change_pct": None,
                        "unit": None,
                        "source": None,
                        "dimension": None,
                        "incompatible_fields": incompatible_fields,
                    }
                )
                continue

            delta = _numeric_delta(before["value"], after["value"])
            status = "unchanged" if before["value"] == after["value"] else "changed"
            changes.append(
                {
                    "finding_id": finding_id,
                    "status": status,
                    "label": after.get("label", before.get("label", finding_id)),
                    "baseline_value": before["value"],
                    "current_value": after["value"],
                    "absolute_delta": 0 if status == "unchanged" else delta,
                    "relative_change_pct": (
                        0.0
                        if status == "unchanged" and float(before["value"]) != 0
                        else _relative_change_pct(before["value"], delta)
                    ),
                    "unit": after.get("unit"),
                    "source": after["source"],
                    "dimension": after.get("dimension"),
                }
            )

        counts = {
            status: sum(change["status"] == status for change in changes)
            for status in ("changed", "unchanged", "added", "removed", "incompatible")
        }
        relation = (
            "same_dataset_version"
            if baseline["dataset_id"] == current["dataset_id"]
            else (
                "same_source_new_version"
                if baseline["dataset_ref"] == current["dataset_ref"]
                and baseline["sheet_name"] == current["sheet_name"]
                else "different_sources"
            )
        )
        manifest = {
            "baseline_run_id": baseline_run_id,
            "current_run_id": current_run_id,
            "changes": changes,
        }
        digest = hashlib.sha256(
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return {
            "schema_version": "analysis-history-comparison.v1",
            "status": "completed",
            "baseline": self._comparison_run_ref(baseline),
            "current": self._comparison_run_ref(current),
            "dataset_relation": relation,
            "period_semantics": "not_inferred",
            "summary": {"total": len(changes), **counts},
            "changes": changes,
            "manifest_sha256": digest,
            "verification": {
                "status": "passed",
                "scope": "archived_verified_finding_manifests",
                "evidence_only": True,
                "errors": [],
            },
        }

    @staticmethod
    def _verified_findings(run: dict[str, Any]) -> list[dict[str, Any]]:
        if run.get("mode") != "agent" or run.get("verifier_status") != "passed":
            raise ValueError("Yalnız verifier-passed Agent kayıtları karşılaştırılabilir")
        raw_findings = run.get("findings")
        if (
            not isinstance(raw_findings, list)
            or not 1 <= len(raw_findings) <= 48
            or run.get("finding_count") != len(raw_findings)
        ):
            raise ValueError("History finding manifesti geçersiz")
        findings = [_safe_finding(finding) for finding in raw_findings]
        if len({finding["finding_id"] for finding in findings}) != len(findings):
            raise ValueError("History finding manifesti tekrar eden finding_id içeriyor")
        return findings

    @staticmethod
    def _comparison_run_ref(run: dict[str, Any]) -> dict[str, Any]:
        return {
            key: run[key]
            for key in (
                "run_id",
                "dataset_id",
                "dataset_ref",
                "source_name",
                "sheet_name",
                "mode",
                "question",
                "run_status",
                "verifier_status",
                "finding_count",
                "tools",
                "created_at",
            )
        }

    @staticmethod
    def _decode_row(row: sqlite3.Row, *, include_findings: bool) -> dict[str, Any]:
        payload = {
            key: row[key]
            for key in (
                "run_id",
                "dataset_id",
                "dataset_ref",
                "source_name",
                "sheet_name",
                "mode",
                "question",
                "run_status",
                "verifier_status",
                "finding_count",
                "created_at",
            )
        }
        payload["tools"] = json.loads(row["tools_json"])
        if include_findings:
            payload["findings"] = json.loads(row["findings_json"])
        return payload
