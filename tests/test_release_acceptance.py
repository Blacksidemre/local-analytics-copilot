from __future__ import annotations

import codecs
import json
from pathlib import Path

from lacopilot.release_acceptance import run_release_acceptance

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_RUNNER = ROOT / "scripts" / "run_release_acceptance.ps1"


def test_offline_release_acceptance_runs_csv_xlsx_reports_and_model_fallback(tmp_path):
    run_root = tmp_path / "acceptance"

    result = run_release_acceptance(run_root=run_root, agent_mode="offline")

    assert result["schema_version"] == "release-acceptance.v1"
    assert result["status"] == "passed_with_skips"
    assert result["agent_mode_requested"] == "offline"
    assert result["agent_mode_executed"] == "deterministic_fallback"
    checks = {check["id"]: check for check in result["checks"]}
    assert checks["local_privacy_configuration"]["status"] == "passed"
    assert {
        key: checks["csv_xlsx_quick_analyst_parity"]["details"][key]
        for key in ("rows", "columns", "missing_cells", "duplicate_copies")
    } == {
        "rows": 1508,
        "columns": 22,
        "missing_cells": 52,
        "duplicate_copies": 8,
    }
    assert checks["analyst_reports"]["status"] == "passed"
    assert checks["model_unavailable_fallback"]["status"] == "passed"
    assert checks["live_agent_csv_xlsx"]["status"] == "skipped"
    assert {Path(path).suffix for path in result["artifacts"]} >= {
        ".csv",
        ".xlsx",
        ".html",
        ".pdf",
    }
    assert all((run_root / "workspace" / path).is_file() for path in result["artifacts"])

    persisted = json.loads((run_root / "acceptance-result.json").read_text(encoding="utf-8"))
    assert persisted == result
    serialized = json.dumps(result, ensure_ascii=False).lower()
    assert "raw_rows" not in serialized
    assert "api_key" not in serialized
    assert "bearer " not in serialized


def test_windows_acceptance_runner_is_utf8_shell_free_and_live_mode_explicit():
    raw = WINDOWS_RUNNER.read_bytes()
    assert raw.startswith(codecs.BOM_UTF8)
    source = raw.decode("utf-8-sig")

    assert '.venv\\Scripts\\python.exe"' in source
    assert 'if ($LiveAgent) { $AgentMode = "live" }' in source
    assert '"lacopilot.release_acceptance", "--agent-mode", $AgentMode' in source
    assert "[Console]::OutputEncoding = $Utf8NoBom" in source
    assert '$env:PYTHONUTF8 = "1"' in source
    assert "Invoke-Expression" not in source
    assert "cmd /c" not in source.lower()
    assert "Start-Process" not in source
