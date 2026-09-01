from __future__ import annotations

import json
import sqlite3

import pytest

from lacopilot.analysis_history import AnalysisHistoryStore


def verified_agent(findings: list[dict] | None = None) -> dict:
    evidence = findings or [
        {
            "finding_id": "profile.shape.rows",
            "kind": "dataset_shape",
            "label": "Satır sayısı",
            "value": 1508,
            "unit": "rows",
            "source": "deterministic_dataframe_shape",
        }
    ]
    return {
        "status": "completed",
        "plan": {
            "steps": [
                {
                    "step_id": "profile",
                    "tool": "profile_dataset",
                    "arguments": {},
                }
            ]
        },
        "run": {
            "status": "completed",
            "verification": {"status": "passed"},
            "synthesis_request": {"status": "ready", "evidence": evidence},
        },
    }


def test_history_stores_only_verified_manifest_and_is_deletable(tmp_path):
    source = tmp_path / "fixture.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    store = AnalysisHistoryStore(tmp_path / "history.sqlite3")
    run_id = store.record_verified_agent_run(
        dataset_ref="incoming/fixture.csv",
        source_path=source,
        sheet_name="0",
        question="Özetle; token=super-secret",
        agent=verified_agent(),
    )

    assert run_id is not None
    listed = store.list_runs()
    assert listed[0]["run_id"] == run_id
    assert listed[0]["finding_count"] == 1
    assert "findings" not in listed[0]
    assert "super-secret" not in listed[0]["question"]
    assert listed[0]["tools"] == ["profile_dataset"]

    archived = store.get_run(run_id)
    assert archived is not None
    assert archived["findings"] == [
        {
            "finding_id": "profile.shape.rows",
            "kind": "dataset_shape",
            "label": "Satır sayısı",
            "value": 1508,
            "unit": "rows",
            "source": "deterministic_dataframe_shape",
        }
    ]
    assert set(archived).isdisjoint({"raw_rows", "records", "sample_rows", "arguments"})
    assert store.delete_run(run_id) is True
    assert store.get_run(run_id) is None


def test_history_rejects_unverified_or_unbounded_runs(tmp_path):
    source = tmp_path / "fixture.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    store = AnalysisHistoryStore(tmp_path / "history.sqlite3")
    agent = verified_agent()
    agent["run"]["verification"]["status"] = "failed"
    assert (
        store.record_verified_agent_run(
            dataset_ref="incoming/fixture.csv",
            source_path=source,
            sheet_name="0",
            question="Özetle",
            agent=agent,
        )
        is None
    )
    assert store.list_runs() == []

    agent = verified_agent()
    agent["run"]["synthesis_request"]["evidence"][0]["raw_rows"] = [[1]]
    try:
        store.record_verified_agent_run(
            dataset_ref="incoming/fixture.csv",
            source_path=source,
            sheet_name="0",
            question="Özetle",
            agent=agent,
        )
    except ValueError as exc:
        assert "typed finding" in str(exc)
    else:  # pragma: no cover - safety assertion
        raise AssertionError("unbounded finding history tarafından reddedilmeliydi")


def finding(
    finding_id: str,
    value: int | float,
    *,
    unit: str = "count",
    source: str = "deterministic_test",
) -> dict:
    return {
        "finding_id": finding_id,
        "kind": "test_metric",
        "label": finding_id,
        "value": value,
        "unit": unit,
        "source": source,
    }


def record_run(store, source, findings):
    run_id = store.record_verified_agent_run(
        dataset_ref="incoming/fixture.csv",
        source_path=source,
        sheet_name="0",
        question="Dönemleri karşılaştır",
        agent=verified_agent(findings),
    )
    assert run_id is not None
    return run_id


def test_history_compares_only_compatible_verified_finding_manifests(tmp_path):
    source = tmp_path / "fixture.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    store = AnalysisHistoryStore(tmp_path / "history.sqlite3")
    baseline_id = record_run(
        store,
        source,
        [
            finding("added_later", 1),
            finding("changed", 100),
            finding("incompatible", 5, unit="rows"),
            finding("removed_later", 9),
            finding("unchanged", 7),
            finding("zero_baseline", 0),
        ],
    )
    source.write_text("a\n1\n2\n", encoding="utf-8")
    current_id = record_run(
        store,
        source,
        [
            finding("added_now", 3),
            finding("added_later", 1),
            finding("changed", 110),
            finding("incompatible", 5, unit="percent"),
            finding("unchanged", 7),
            finding("zero_baseline", 2),
        ],
    )

    comparison = store.compare_runs(baseline_id, current_id)

    assert comparison["schema_version"] == "analysis-history-comparison.v1"
    assert comparison["dataset_relation"] == "same_source_new_version"
    assert comparison["period_semantics"] == "not_inferred"
    assert comparison["summary"] == {
        "total": 7,
        "changed": 2,
        "unchanged": 2,
        "added": 1,
        "removed": 1,
        "incompatible": 1,
    }
    assert comparison["verification"] == {
        "status": "passed",
        "scope": "archived_verified_finding_manifests",
        "evidence_only": True,
        "errors": [],
    }
    assert comparison["baseline"]["run_status"] == "completed"
    assert comparison["baseline"]["tools"] == ["profile_dataset"]
    assert len(comparison["manifest_sha256"]) == 64
    assert [change["finding_id"] for change in comparison["changes"]] == sorted(
        change["finding_id"] for change in comparison["changes"]
    )
    by_id = {change["finding_id"]: change for change in comparison["changes"]}
    assert by_id["changed"]["absolute_delta"] == 10
    assert by_id["changed"]["relative_change_pct"] == 10.0
    assert by_id["zero_baseline"]["relative_change_pct"] is None
    assert by_id["incompatible"]["incompatible_fields"] == ["unit"]
    assert by_id["removed_later"]["status"] == "removed"
    assert by_id["added_now"]["status"] == "added"
    assert set(comparison).isdisjoint({"raw_rows", "records", "sample_rows", "prompt"})

    with pytest.raises(ValueError, match="iki farklı"):
        store.compare_runs(baseline_id, baseline_id)


def test_history_comparison_fails_closed_for_tampered_archive(tmp_path):
    source = tmp_path / "fixture.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    database = tmp_path / "history.sqlite3"
    store = AnalysisHistoryStore(database)
    baseline_id = record_run(store, source, [finding("metric", 1)])
    current_id = record_run(store, source, [finding("metric", 2)])

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE analysis_runs SET verifier_status='failed' WHERE run_id=?",
            (current_id,),
        )
    with pytest.raises(ValueError, match="verifier-passed"):
        store.compare_runs(baseline_id, current_id)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE analysis_runs SET verifier_status='passed', findings_json=? WHERE run_id=?",
            (json.dumps([finding("metric", float("nan"))]), current_id),
        )
    with pytest.raises(ValueError, match="finite deterministic numeric"):
        store.compare_runs(baseline_id, current_id)
