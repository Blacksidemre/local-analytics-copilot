from __future__ import annotations

from lacopilot.analysis_history import AnalysisHistoryStore


def verified_agent() -> dict:
    finding = {
        "finding_id": "profile.shape.rows",
        "kind": "dataset_shape",
        "label": "Satır sayısı",
        "value": 1508,
        "unit": "rows",
        "source": "deterministic_dataframe_shape",
    }
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
            "synthesis_request": {"status": "ready", "evidence": [finding]},
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
