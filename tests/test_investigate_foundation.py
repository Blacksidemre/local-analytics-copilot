from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from lacopilot.config import get_settings
from lacopilot.investigate_foundation import (
    BoundedInvestigateExecutor,
    ExecutionBudget,
    InvestigateContext,
    InvestigatePlan,
    build_local_planner_messages,
    parse_local_planner_output,
    verify_investigate_run,
    verify_tool_result,
)
from lacopilot.regression_fixture import write_credit_risk_regression_fixture


def configure(tmp_path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LAC_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    return get_settings()


def context() -> InvestigateContext:
    return InvestigateContext(
        dataset_ref="incoming/test.csv",
        columns=[
            {"name": "target", "role": "numeric", "unique": 2, "missing": 0},
            {"name": "value", "role": "numeric", "unique": 24, "missing": 0},
        ],
        approved_target_columns=["target"],
        approved_target_kinds={"target": "binary"},
        approved_predictor_columns=["value"],
    )


def plan_payload(*, steps: list[dict[str, Any]], criteria=None) -> dict[str, Any]:
    return {
        "schema_version": "investigate-plan.v1",
        "objective": "Hedefle ilişkili faktörleri kanıta bağlı tara.",
        "dataset_ref": "incoming/test.csv",
        "sheet_name": None,
        "approved_target_columns": ["target"],
        "approved_target_kinds": {"target": "binary"},
        "approved_predictor_columns": ["value"],
        "completion_criteria": criteria or ["profile_verified", "target_screen_verified"],
        "steps": steps,
    }


def profile_step(step_id="profile", depends_on=None):
    return {
        "step_id": step_id,
        "purpose": "Veri kalitesini doğrula.",
        "depends_on": depends_on or [],
        "tool": "profile_dataset",
        "arguments": {},
    }


def target_step(step_id="screen", depends_on=None, predictor_selection="explicit_user"):
    arguments: dict[str, Any] = {
        "target_column": "target",
        "target_kind": "binary",
        "predictor_selection": predictor_selection,
    }
    if predictor_selection == "explicit_user":
        arguments["predictor_columns"] = ["value"]
    return {
        "step_id": step_id,
        "purpose": "Onaylı hedef için deterministik ilişki taraması yap.",
        "depends_on": depends_on or [],
        "tool": "screen_target_associations",
        "arguments": arguments,
    }


def valid_profile_result():
    summary = {
        "rows": 2,
        "columns": 2,
        "total_cells": 4,
        "total_missing_cells": 0,
        "missing_cell_pct": 0.0,
        "exact_duplicate_copies": 0,
        "duplicate_rows_including_originals": 0,
        "quality_score_heuristic": 100.0,
        "roles": {"numeric": 2},
        "constant_columns": [],
        "high_missing_columns": [],
    }
    specs = [
        ("profile.shape.rows", 2, "rows", "deterministic_dataframe_shape"),
        ("profile.shape.columns", 2, "columns", "deterministic_dataframe_shape"),
        ("profile.quality.missing_cells", 0, "cells", "dataframe_isna_sum"),
        (
            "profile.quality.missing_cell_rate",
            0.0,
            "percent_of_all_cells",
            "total_missing_cells_divided_by_rows_times_columns",
        ),
        (
            "profile.quality.exact_duplicate_copies",
            0,
            "rows",
            "dataframe_duplicated_keep_first",
        ),
        (
            "profile.quality.duplicate_group_rows",
            0,
            "rows",
            "dataframe_duplicated_keep_false",
        ),
        (
            "profile.quality.score_heuristic",
            100.0,
            "score_0_100",
            "documented_screening_heuristic",
        ),
    ]
    return {
        "schema_version": "profile-evidence.v1",
        "summary": summary,
        "findings": [
            {"finding_id": finding_id, "value": value, "unit": unit, "source": source}
            for finding_id, value, unit, source in specs
        ],
        "verification": {"status": "passed", "errors": []},
    }


def nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for nested in value.values() for key in nested_keys(nested)}
    if isinstance(value, list):
        return {key for nested in value for key in nested_keys(nested)}
    return set()


def test_planner_contract_rejects_unknown_tools_paths_and_unapproved_semantics():
    base = plan_payload(steps=[profile_step()], criteria=["profile_verified"])

    with pytest.raises(ValidationError):
        InvestigatePlan.model_validate(
            {**base, "steps": [{**profile_step(), "tool": "python", "arguments": {}}]}
        )
    with pytest.raises(ValidationError, match="workspace-relative"):
        InvestigatePlan.model_validate({**base, "dataset_ref": "../secret.csv"})
    with pytest.raises(ValidationError, match="onaylanmamış"):
        InvestigatePlan.model_validate(
            {
                **base,
                "completion_criteria": ["target_screen_verified"],
                "steps": [
                    {
                        **target_step(),
                        "arguments": {
                            **target_step()["arguments"],
                            "target_column": "invented_target",
                        },
                    }
                ],
            }
        )
    with pytest.raises(ValidationError, match="target_kind"):
        InvestigatePlan.model_validate(
            {
                **base,
                "completion_criteria": ["target_screen_verified"],
                "steps": [
                    {
                        **target_step(),
                        "arguments": {
                            **target_step()["arguments"],
                            "target_kind": "continuous",
                        },
                    }
                ],
            }
        )
    with pytest.raises(ValidationError, match="tekrar eden sütun"):
        InvestigateContext(
            dataset_ref="incoming/test.csv",
            columns=[
                {"name": "same", "role": "numeric", "unique": 2, "missing": 0},
                {"name": "same", "role": "numeric", "unique": 3, "missing": 0},
            ],
        )


def test_local_planner_is_schema_only_and_cannot_change_fixed_context():
    fixed = context()
    messages = build_local_planner_messages("İlişkileri araştır.", fixed)
    assert "Never calculate a number" in messages[0]["content"]
    assert "shell" in messages[0]["content"]
    assert "raw rows" in messages[0]["content"]
    assert "output_schema" in json.loads(messages[1]["content"])

    payload = plan_payload(steps=[profile_step()], criteria=["profile_verified"])
    assert parse_local_planner_output(payload, fixed).dataset_ref == fixed.dataset_ref
    with pytest.raises(ValueError, match="sabit context"):
        parse_local_planner_output({**payload, "sheet_name": "Other"}, fixed)


def test_executor_stops_after_goal_and_blocks_duplicate_calls(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    (settings.incoming_dir / "test.csv").write_text("target,value\n0,1\n1,2\n", encoding="utf-8")
    calls = []

    def profile_handler(_plan, _step):
        calls.append("profile")
        return valid_profile_result()

    executor = BoundedInvestigateExecutor(registry={"profile_dataset": profile_handler})
    goal_plan = InvestigatePlan.model_validate(
        plan_payload(
            steps=[profile_step("first"), profile_step("never_run")],
            criteria=["profile_verified"],
        )
    )
    completed = executor.run(goal_plan)
    assert completed["status"] == "completed"
    assert completed["stop_reason"] == "goal_completed"
    assert calls == ["profile"]

    duplicate_plan = InvestigatePlan.model_validate(
        plan_payload(
            steps=[profile_step("first"), profile_step("duplicate"), target_step()],
        )
    )
    stopped = executor.run(duplicate_plan)
    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "duplicate_tool_call"
    assert stopped["events"][-1]["error"]["code"] == "duplicate_tool_call"


def test_executor_enforces_failure_budget_and_blocks_unverified_evidence(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    (settings.incoming_dir / "test.csv").write_text("target,value\n0,1\n1,2\n", encoding="utf-8")

    def invalid_profile(_plan, _step):
        result = valid_profile_result()
        result["findings"][0].pop("source")
        return result

    invalid_run = BoundedInvestigateExecutor(
        budget=ExecutionBudget(max_failed_calls=1),
        registry={"profile_dataset": invalid_profile},
    ).run(
        InvestigatePlan.model_validate(
            plan_payload(steps=[profile_step()], criteria=["profile_verified"])
        )
    )
    assert invalid_run["status"] == "stopped"
    assert invalid_run["stop_reason"] == "failure_budget_exhausted"
    assert invalid_run["evidence"] == []
    assert invalid_run["verification"]["status"] == "failed"
    assert invalid_run["synthesis_request"]["status"] == "blocked"
    assert invalid_run["synthesis_request"]["evidence"] == []

    tampered_profile = valid_profile_result()
    tampered_profile["summary"]["exact_duplicate_copies"] = 1
    tampered = verify_tool_result("profile_dataset", tampered_profile)
    assert tampered["status"] == "failed"
    assert {error["code"] for error in tampered["errors"]} & {
        "profile_core_mismatch",
        "invalid_profile_duplicates",
        "invalid_profile_quality_score",
    }
    unbounded_profile = valid_profile_result()
    unbounded_profile["findings"][0]["raw_payload"] = [["hidden"]]
    assert verify_tool_result("profile_dataset", unbounded_profile)["status"] == "failed"


def test_tool_and_run_verifiers_recompute_claims_and_reject_conflicts():
    forged_analyst = {
        "schema_version": "analyst.v1",
        "target_semantics": {
            "column": "target",
            "statistical_role": "binary",
            "selection_source": "explicit_request",
            "business_meaning_status": "unverified",
            "business_meaning": None,
        },
        "kpi_selection": {
            "status": "requires_approved_definition",
            "selected": [],
        },
        "predictor_selection": {},
        "multiple_testing": {
            "method": "benjamini_hochberg",
            "family": "all_executed_target_association_tests",
        },
        "analyses": [],
        "findings": [
            {
                "finding_id": "forged.effect",
                "value": 99,
                "source": "model_claim",
            }
        ],
        "dashboard": {
            "schema_version": 1,
            "cards": [],
            "ranking_basis": "adjusted_p_value_then_finding_id",
            "evidence_policy": "all_numeric_cards_bound_to_finding_id",
        },
        "verification": {"status": "passed", "errors": []},
    }
    verification = verify_tool_result("screen_target_associations", forged_analyst)
    assert verification["status"] == "failed"
    assert "analyst_verification_failed" in {error["code"] for error in verification["errors"]}

    first = valid_profile_result()
    second = valid_profile_result()
    second["findings"][0]["value"] = 999
    run = {
        "events": [
            {
                "step_id": "first",
                "tool": "profile_dataset",
                "status": "completed",
                "verification": {"status": "passed"},
                "result": first,
            },
            {
                "step_id": "second",
                "tool": "profile_dataset",
                "status": "completed",
                "verification": {"status": "passed"},
                "result": second,
            },
        ],
        "evidence": second["findings"],
    }
    run_verification = verify_investigate_run(run)
    assert run_verification["status"] == "failed"
    assert "conflicting_step_evidence" in {error["code"] for error in run_verification["errors"]}


@pytest.mark.parametrize("fixture_format", ["csv", "xlsx"])
def test_default_executor_runs_profile_and_target_screen_without_raw_rows(
    tmp_path, monkeypatch, fixture_format
):
    settings = configure(tmp_path, monkeypatch)
    paths = write_credit_risk_regression_fixture(settings.incoming_dir)
    payload = plan_payload(
        steps=[
            profile_step(),
            {
                **target_step(depends_on=["profile"]),
                "arguments": {
                    "target_column": "default_next_30d",
                    "target_kind": "binary",
                    "predictor_selection": "explicit_user",
                    "predictor_columns": ["utilization_rate", "customer_segment"],
                },
            },
        ]
    )
    payload.update(
        {
            "dataset_ref": f"incoming/{paths[fixture_format].name}",
            "approved_target_columns": ["default_next_30d"],
            "approved_target_kinds": {"default_next_30d": "binary"},
            "approved_predictor_columns": ["utilization_rate", "customer_segment"],
        }
    )
    run = BoundedInvestigateExecutor().run(InvestigatePlan.model_validate(payload))

    assert run["status"] == "completed"
    assert run["stop_reason"] == "goal_completed"
    assert run["verification"]["status"] == "passed"
    assert run["synthesis_request"]["mode"] == "tool_less"
    assert run["synthesis_request"]["status"] == "ready"
    assert run["synthesis_request"]["evidence_scope"]["included"] <= 48
    assert run["synthesis_request"]["evidence_scope"]["verified_total"] == len(run["evidence"])
    assert {finding["finding_id"] for finding in run["synthesis_request"]["evidence"]} <= {
        finding["finding_id"] for finding in run["evidence"]
    }
    assert all(finding["finding_id"] and finding["source"] for finding in run["evidence"])
    result_keys = {
        key
        for event in run["events"]
        if event["status"] == "completed"
        for key in nested_keys(event["result"])
    }
    assert {"categorical_top_values", "numeric_summary", "raw_rows", "records"}.isdisjoint(
        result_keys
    )
