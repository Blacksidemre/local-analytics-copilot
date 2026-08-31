from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lacopilot.app import app
from lacopilot.config import get_settings
from lacopilot.regression_fixture import write_credit_risk_regression_fixture


def nested_keys(value):
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in nested_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in nested_keys(item)}
    return set()


def configure(tmp_path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LAC_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("LAC_API_TOKEN", raising=False)
    get_settings.cache_clear()
    return get_settings()


def planner_payload(dataset_ref: str) -> str:
    return json.dumps(
        {
            "schema_version": "investigate-plan.v1",
            "objective": "Deterministik veri profilini özetle.",
            "dataset_ref": dataset_ref,
            "sheet_name": "0",
            "approved_target_columns": [],
            "approved_target_kinds": {},
            "approved_predictor_columns": [],
            "completion_criteria": ["profile_verified"],
            "steps": [
                {
                    "step_id": "profile",
                    "purpose": "Veri kalitesini doğrula.",
                    "depends_on": [],
                    "tool": "profile_dataset",
                    "arguments": {},
                }
            ],
        },
        ensure_ascii=False,
    )


def synthesis_payload() -> str:
    return json.dumps(
        {
            "schema_version": "investigate-synthesis.v1",
            "summary": [
                {
                    "text": "Veri setinde 1508 satır bulunuyor.",
                    "finding_ids": ["profile.shape.rows"],
                }
            ],
            "limitations": ["İş anlamı onaylı metadata olmadan belirlenemiyor."],
            "recommended_next_step": None,
        },
        ensure_ascii=False,
    )


def test_agent_api_runs_local_planner_and_returns_verified_fallback(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    dataset = write_credit_risk_regression_fixture(settings.incoming_dir)["csv"]
    dataset_ref = f"incoming/{dataset.name}"
    outputs = iter([planner_payload(dataset_ref), synthesis_payload()])

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def chat(self, **_kwargs):
            return SimpleNamespace(message=SimpleNamespace(content=next(outputs)))

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=FakeClient))
    response = TestClient(app).post(
        "/api/v1/analysis/agent",
        json={"file_path": dataset_ref, "question": "Bu veri setini özetle."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "agent-api.v1"
    assert payload["status"] == "completed"
    assert payload["dataset"] == {
        "rows": 1508,
        "columns": 22,
        "total_missing_cells": 52,
        "missing_cell_pct": 0.1567,
        "exact_duplicate_copies": 8,
        "schema": payload["dataset"]["schema"],
    }
    assert payload["agent"]["run"]["verification"]["status"] == "passed"
    assert payload["agent"]["synthesis"]["verification"]["status"] == "passed"
    assert payload["history"]["status"] == "saved"
    assert "raw_rows" not in nested_keys(payload)

    history = TestClient(app).get("/api/v1/analysis/history").json()
    assert len(history["runs"]) == 1
    run_id = history["runs"][0]["run_id"]
    archived = TestClient(app).get(f"/api/v1/analysis/history/{run_id}").json()
    assert archived["run"]["verifier_status"] == "passed"
    assert archived["run"]["findings"]
    deleted = TestClient(app).delete(f"/api/v1/analysis/history/{run_id}")
    assert deleted.status_code == 200


def test_agent_api_model_unavailable_keeps_deterministic_dashboard(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    dataset = write_credit_risk_regression_fixture(settings.incoming_dir)["csv"]

    class OfflineClient:
        def __init__(self, **_kwargs):
            pass

        def chat(self, **_kwargs):
            raise ConnectionError("private host detail")

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=OfflineClient))
    response = TestClient(app).post(
        "/api/v1/analysis/agent",
        json={
            "file_path": f"incoming/{dataset.name}",
            "question": "Sorunları bul.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "planner_unavailable"
    assert payload["dataset"]["rows"] == 1508
    assert payload["dashboard"]["cards"]
    assert all(card["source"] for card in payload["dashboard"]["cards"])
    assert payload["history"] == {"status": "not_saved", "reason": "run_not_verified"}
    assert "private host detail" not in response.text


def test_agent_api_requires_complete_explicit_target_semantics(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    dataset = write_credit_risk_regression_fixture(settings.incoming_dir)["csv"]
    response = TestClient(app).post(
        "/api/v1/analysis/agent",
        json={
            "file_path": f"incoming/{dataset.name}",
            "question": "Hedefi incele.",
            "target_column": "default_next_30d",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "incomplete_target_semantics"
    assert response.json()["detail"]["recoverable"] is True
