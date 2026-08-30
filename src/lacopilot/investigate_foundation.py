from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lacopilot.analyst_pipeline import run_analyst_pipeline, verify_analyst_payload
from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.data_tools import profile_dataset

_STEP_ID = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_WINDOWS_DRIVE = re.compile(r"^[a-zA-Z]:")
_PROFILE_REQUIRED_FINDINGS = {
    "profile.shape.rows",
    "profile.shape.columns",
    "profile.quality.missing_cells",
    "profile.quality.missing_cell_rate",
    "profile.quality.exact_duplicate_copies",
    "profile.quality.duplicate_group_rows",
    "profile.quality.score_heuristic",
}
_PROFILE_SUMMARY_KEYS = {
    "rows",
    "columns",
    "total_cells",
    "total_missing_cells",
    "missing_cell_pct",
    "exact_duplicate_copies",
    "duplicate_rows_including_originals",
    "quality_score_heuristic",
    "roles",
    "constant_columns",
    "high_missing_columns",
}
_PROFILE_CORE_SPECS = {
    "profile.shape.rows": ("rows", "rows", "deterministic_dataframe_shape"),
    "profile.shape.columns": ("columns", "columns", "deterministic_dataframe_shape"),
    "profile.quality.missing_cells": (
        "total_missing_cells",
        "cells",
        "dataframe_isna_sum",
    ),
    "profile.quality.missing_cell_rate": (
        "missing_cell_pct",
        "percent_of_all_cells",
        "total_missing_cells_divided_by_rows_times_columns",
    ),
    "profile.quality.exact_duplicate_copies": (
        "exact_duplicate_copies",
        "rows",
        "dataframe_duplicated_keep_first",
    ),
    "profile.quality.duplicate_group_rows": (
        "duplicate_rows_including_originals",
        "rows",
        "dataframe_duplicated_keep_false",
    ),
    "profile.quality.score_heuristic": (
        "quality_score_heuristic",
        "score_0_100",
        "documented_screening_heuristic",
    ),
}
_PROFILE_RESULT_KEYS = {"schema_version", "summary", "findings", "verification"}
_ANALYST_RESULT_KEYS = {
    "schema_version",
    "target_semantics",
    "kpi_selection",
    "predictor_selection",
    "multiple_testing",
    "analyses",
    "findings",
    "dashboard",
    "verification",
}
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
_MAX_SYNTHESIS_FINDINGS = 48
_FORBIDDEN_RESULT_KEYS = {
    "categorical_top_values",
    "data",
    "numeric_summary",
    "raw_rows",
    "records",
    "sample_rows",
}

CompletionCriterion = Literal["profile_verified", "target_screen_verified"]
TargetKind = Literal["binary", "continuous", "categorical"]
PredictorSelection = Literal["deterministic_role_filter", "explicit_user"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlannerColumnFact(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    role: Literal["numeric", "categorical", "datetime", "identifier", "text", "boolean"]
    unique: int = Field(ge=0)
    missing: int = Field(ge=0)


class InvestigateContext(StrictModel):
    dataset_ref: str = Field(min_length=1, max_length=1000)
    sheet_name: str | None = Field(default=None, max_length=256)
    columns: list[PlannerColumnFact] = Field(min_length=1, max_length=200)
    approved_target_columns: list[str] = Field(default_factory=list, max_length=5)
    approved_target_kinds: dict[str, TargetKind] = Field(default_factory=dict, max_length=5)
    approved_predictor_columns: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("dataset_ref")
    @classmethod
    def dataset_must_be_workspace_relative(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or _WINDOWS_DRIVE.match(normalized) or ".." in path.parts:
            raise ValueError("dataset_ref workspace-relative olmalı")
        return normalized

    @model_validator(mode="after")
    def approved_columns_must_exist(self) -> InvestigateContext:
        column_names = [column.name for column in self.columns]
        if len(column_names) != len(set(column_names)):
            raise ValueError("columns tekrar eden sütun adı içeremez")
        known = {column.name for column in self.columns}
        for label, values in (
            ("approved_target_columns", self.approved_target_columns),
            ("approved_predictor_columns", self.approved_predictor_columns),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} tekrar eden sütun içeremez")
            unknown = sorted(set(values) - known)
            if unknown:
                raise ValueError(f"{label} bilinmeyen sütun içeriyor: {unknown}")
        unknown_target_kinds = sorted(
            set(self.approved_target_kinds) - set(self.approved_target_columns)
        )
        if unknown_target_kinds:
            raise ValueError(
                f"approved_target_kinds onaylanmamış hedef içeriyor: {unknown_target_kinds}"
            )
        return self


class ProfileArguments(StrictModel):
    pass


class TargetAssociationArguments(StrictModel):
    target_column: str = Field(min_length=1, max_length=256)
    target_kind: TargetKind | None = None
    predictor_selection: PredictorSelection = "deterministic_role_filter"
    predictor_columns: list[str] | None = Field(default=None, min_length=1, max_length=20)

    @model_validator(mode="after")
    def predictor_contract(self) -> TargetAssociationArguments:
        if self.predictor_selection == "explicit_user" and not self.predictor_columns:
            raise ValueError("explicit_user seçimi predictor_columns gerektirir")
        if self.predictor_selection == "deterministic_role_filter" and self.predictor_columns:
            raise ValueError("deterministic_role_filter predictor_columns kabul etmez")
        if self.predictor_columns and len(self.predictor_columns) != len(
            set(self.predictor_columns)
        ):
            raise ValueError("predictor_columns tekrar eden sütun içeremez")
        if self.predictor_columns and self.target_column in self.predictor_columns:
            raise ValueError("hedef sütun predictor olamaz")
        return self


class StepBase(StrictModel):
    step_id: str = Field(min_length=1, max_length=48)
    purpose: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("step_id")
    @classmethod
    def valid_step_id(cls, value: str) -> str:
        if not _STEP_ID.fullmatch(value):
            raise ValueError("step_id küçük harf, rakam ve alt çizgi içermeli")
        return value


class ProfileStep(StepBase):
    tool: Literal["profile_dataset"]
    arguments: ProfileArguments = Field(default_factory=ProfileArguments)


class TargetAssociationStep(StepBase):
    tool: Literal["screen_target_associations"]
    arguments: TargetAssociationArguments


InvestigateStep = Annotated[
    ProfileStep | TargetAssociationStep,
    Field(discriminator="tool"),
]


class InvestigatePlan(StrictModel):
    schema_version: Literal["investigate-plan.v1"] = "investigate-plan.v1"
    objective: str = Field(min_length=1, max_length=1000)
    dataset_ref: str = Field(min_length=1, max_length=1000)
    sheet_name: str | None = Field(default=None, max_length=256)
    approved_target_columns: list[str] = Field(default_factory=list, max_length=5)
    approved_target_kinds: dict[str, TargetKind] = Field(default_factory=dict, max_length=5)
    approved_predictor_columns: list[str] = Field(default_factory=list, max_length=20)
    completion_criteria: list[CompletionCriterion] = Field(min_length=1, max_length=2)
    steps: list[InvestigateStep] = Field(min_length=1, max_length=6)

    @field_validator("dataset_ref")
    @classmethod
    def dataset_must_be_workspace_relative(cls, value: str) -> str:
        return InvestigateContext.dataset_must_be_workspace_relative(value)

    @model_validator(mode="after")
    def plan_contract(self) -> InvestigatePlan:
        if len(self.completion_criteria) != len(set(self.completion_criteria)):
            raise ValueError("completion_criteria tekrar edemez")
        if len(self.approved_target_columns) != len(set(self.approved_target_columns)):
            raise ValueError("approved_target_columns tekrar edemez")
        if len(self.approved_predictor_columns) != len(set(self.approved_predictor_columns)):
            raise ValueError("approved_predictor_columns tekrar edemez")
        unknown_target_kinds = sorted(
            set(self.approved_target_kinds) - set(self.approved_target_columns)
        )
        if unknown_target_kinds:
            raise ValueError(
                f"approved_target_kinds onaylanmamış hedef içeriyor: {unknown_target_kinds}"
            )

        seen: set[str] = set()
        produced: set[CompletionCriterion] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"tekrar eden step_id: {step.step_id}")
            unknown_dependencies = sorted(set(step.depends_on) - seen)
            if unknown_dependencies:
                raise ValueError(
                    f"{step.step_id} yalnız önceki adımlara bağlanabilir: {unknown_dependencies}"
                )
            if len(step.depends_on) != len(set(step.depends_on)):
                raise ValueError(f"{step.step_id} tekrar eden dependency içeriyor")
            seen.add(step.step_id)
            if isinstance(step, ProfileStep):
                produced.add("profile_verified")
                continue

            produced.add("target_screen_verified")
            arguments = step.arguments
            if arguments.target_column not in self.approved_target_columns:
                raise ValueError(
                    f"hedef sütun kullanıcı tarafından onaylanmamış: {arguments.target_column}"
                )
            approved_kind = self.approved_target_kinds.get(arguments.target_column)
            if arguments.target_kind != approved_kind:
                raise ValueError(
                    "target_kind kullanıcı/deterministik context ile onaylanmamış: "
                    f"{arguments.target_column}"
                )
            if arguments.predictor_selection == "explicit_user":
                unknown_predictors = sorted(
                    set(arguments.predictor_columns or []) - set(self.approved_predictor_columns)
                )
                if unknown_predictors:
                    raise ValueError(
                        "predictor sütunları kullanıcı tarafından onaylanmamış: "
                        f"{unknown_predictors}"
                    )

        missing_producers = sorted(set(self.completion_criteria) - produced)
        if missing_producers:
            raise ValueError(f"completion criterion üreten adım yok: {missing_producers}")
        return self


def build_local_planner_messages(
    user_request: str,
    context: InvestigateContext,
) -> list[dict[str, str]]:
    if not user_request.strip():
        raise ValueError("user_request boş olamaz")
    if len(user_request) > 4000:
        raise ValueError("user_request 4000 karakter sınırını aşıyor")
    system = (
        "You are a local analytics planner. Return one JSON object matching the supplied schema. "
        "Use only the two allowlisted typed tools. Never calculate a number, invent a KPI or "
        "business meaning, infer an unapproved target, request Python/shell/SQL, or include raw "
        "rows. Use deterministic_role_filter unless predictors were explicitly approved. Keep "
        "the plan at six steps or fewer. The executor, not you, produces every numeric fact."
    )
    user_payload = {
        "request": user_request,
        "fixed_context": context.model_dump(mode="json"),
        "output_schema": InvestigatePlan.model_json_schema(),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def parse_local_planner_output(
    payload: str | dict[str, Any],
    context: InvestigateContext,
) -> InvestigatePlan:
    plan = (
        InvestigatePlan.model_validate_json(payload)
        if isinstance(payload, str)
        else InvestigatePlan.model_validate(payload)
    )
    fixed_values = {
        "dataset_ref": context.dataset_ref,
        "sheet_name": context.sheet_name,
        "approved_target_columns": context.approved_target_columns,
        "approved_target_kinds": context.approved_target_kinds,
        "approved_predictor_columns": context.approved_predictor_columns,
    }
    for field, expected in fixed_values.items():
        if getattr(plan, field) != expected:
            raise ValueError(f"planner sabit context alanını değiştirdi: {field}")
    return plan


@dataclass(frozen=True)
class ExecutionBudget:
    max_steps: int = 6
    max_failed_calls: int = 2

    def __post_init__(self) -> None:
        if not 1 <= self.max_steps <= 6:
            raise ValueError("max_steps 1 ile 6 arasında olmalı")
        if not 1 <= self.max_failed_calls <= 3:
            raise ValueError("max_failed_calls 1 ile 3 arasında olmalı")


ToolHandler = Callable[[InvestigatePlan, InvestigateStep], dict[str, Any]]


def _profile_tool(plan: InvestigatePlan, _step: InvestigateStep) -> dict[str, Any]:
    profile = profile_dataset(plan.dataset_ref, plan.sheet_name or "0")
    return {
        "schema_version": "profile-evidence.v1",
        "summary": {
            "rows": profile["rows"],
            "columns": profile["columns"],
            "total_cells": profile["total_cells"],
            "total_missing_cells": profile["total_missing_cells"],
            "missing_cell_pct": profile["missing_cell_pct"],
            "exact_duplicate_copies": profile["duplicate_rows"],
            "duplicate_rows_including_originals": profile["duplicate_rows_including_originals"],
            "quality_score_heuristic": profile["quality_score_heuristic"],
            "roles": {role: len(columns) for role, columns in profile["roles"].items()},
            "constant_columns": profile["constant_columns"],
            "high_missing_columns": profile["high_missing_columns"],
        },
        "findings": profile["findings"],
        "verification": {
            "status": "passed",
            "scope": "deterministic_profile_findings_without_raw_rows",
            "errors": [],
        },
    }


def _target_association_tool(
    plan: InvestigatePlan,
    step: InvestigateStep,
) -> dict[str, Any]:
    if not isinstance(step, TargetAssociationStep):  # pragma: no cover - registry invariant
        raise TypeError("screen_target_associations TargetAssociationStep gerektirir")
    arguments = step.arguments
    payload = run_analyst_pipeline(
        plan.dataset_ref,
        arguments.target_column,
        sheet_name=plan.sheet_name or "0",
        target_kind=arguments.target_kind,
        predictor_columns=arguments.predictor_columns,
        interpret=False,
    )
    return {
        "schema_version": payload["schema_version"],
        "target_semantics": payload["target_semantics"],
        "kpi_selection": payload["kpi_selection"],
        "predictor_selection": payload["predictor_selection"],
        "multiple_testing": payload["multiple_testing"],
        "analyses": payload["analyses"],
        "findings": payload["findings"],
        "dashboard": payload["dashboard"],
        "verification": payload["verification"],
    }


DEFAULT_TOOL_REGISTRY: dict[str, ToolHandler] = {
    "profile_dataset": _profile_tool,
    "screen_target_associations": _target_association_tool,
}


def _forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in _FORBIDDEN_RESULT_KEYS:
                found.add(str(key))
            found.update(_forbidden_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return found


def _verify_findings(findings: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(findings, list) or not findings:
        return [{"code": "missing_findings", "message": "Tool sonucu finding içermiyor"}]
    seen: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            errors.append({"code": "invalid_finding", "message": "Finding object olmalı"})
            continue
        extra_keys = sorted(set(finding) - _FINDING_KEYS)
        if extra_keys:
            errors.append({"code": "unbounded_finding_contract", "message": ", ".join(extra_keys)})
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            errors.append({"code": "invalid_finding_id", "message": str(finding_id)})
            continue
        if finding_id in seen:
            errors.append({"code": "duplicate_finding_id", "message": finding_id})
        seen.add(finding_id)
        value = finding.get("value")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            errors.append({"code": "invalid_numeric_value", "message": finding_id})
        if not isinstance(finding.get("source"), str) or not finding["source"]:
            errors.append({"code": "missing_finding_source", "message": finding_id})
        dimension = finding.get("dimension")
        if dimension is not None and (
            not isinstance(dimension, dict)
            or len(dimension) > 3
            or any(
                not isinstance(key, str) or not isinstance(item, str)
                for key, item in dimension.items()
            )
        ):
            errors.append({"code": "invalid_finding_dimension", "message": finding_id})
    return errors


def _verify_profile_result(result: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if set(result) != _PROFILE_RESULT_KEYS:
        errors.append({"code": "invalid_profile_contract", "message": "top-level keys"})
    summary = result.get("summary")
    if not isinstance(summary, dict) or set(summary) != _PROFILE_SUMMARY_KEYS:
        return errors + [{"code": "invalid_profile_contract", "message": "summary"}]

    findings = result.get("findings")
    if not isinstance(findings, list):
        return errors
    finding_index = {
        finding.get("finding_id"): finding
        for finding in findings
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str)
    }
    for finding_id, (summary_key, unit, source) in _PROFILE_CORE_SPECS.items():
        finding = finding_index.get(finding_id)
        if finding is None:
            continue
        if (
            finding.get("value") != summary.get(summary_key)
            or finding.get("unit") != unit
            or finding.get("source") != source
        ):
            errors.append({"code": "profile_core_mismatch", "message": finding_id})

    rows = summary.get("rows")
    columns = summary.get("columns")
    total_cells = summary.get("total_cells")
    total_missing = summary.get("total_missing_cells")
    missing_pct = summary.get("missing_cell_pct")
    duplicate_copies = summary.get("exact_duplicate_copies")
    duplicate_group_rows = summary.get("duplicate_rows_including_originals")
    quality_score = summary.get("quality_score_heuristic")
    integer_values = (
        rows,
        columns,
        total_cells,
        total_missing,
        duplicate_copies,
        duplicate_group_rows,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in integer_values):
        errors.append({"code": "invalid_profile_summary_numeric", "message": "integer fields"})
        return errors
    if rows < 0 or columns < 0 or total_cells != rows * columns:
        errors.append({"code": "invalid_profile_shape", "message": "rows x columns"})
    if not 0 <= total_missing <= total_cells:
        errors.append({"code": "invalid_profile_missing", "message": "total_missing_cells"})
    expected_missing_pct = round(total_missing / max(total_cells, 1) * 100, 4)
    if (
        isinstance(missing_pct, bool)
        or not isinstance(missing_pct, (int, float))
        or not math.isclose(float(missing_pct), expected_missing_pct, abs_tol=1e-9)
    ):
        errors.append({"code": "invalid_profile_missing", "message": "missing_cell_pct"})
    if not 0 <= duplicate_copies <= duplicate_group_rows <= rows:
        errors.append({"code": "invalid_profile_duplicates", "message": "duplicate semantics"})

    constant_columns = summary.get("constant_columns")
    high_missing_columns = summary.get("high_missing_columns")
    roles = summary.get("roles")
    if (
        not isinstance(constant_columns, list)
        or not isinstance(high_missing_columns, list)
        or not isinstance(roles, dict)
        or any(not isinstance(column, str) for column in constant_columns)
        or any(not isinstance(column, str) for column in high_missing_columns)
        or len(constant_columns) != len(set(constant_columns))
        or len(high_missing_columns) != len(set(high_missing_columns))
        or any(not isinstance(role, str) for role in roles)
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in roles.values()
        )
        or sum(roles.values()) != columns
        or len(constant_columns) > columns
        or len(high_missing_columns) > columns
    ):
        errors.append({"code": "invalid_profile_dimensions", "message": "roles or columns"})
        constant_count = 0
    else:
        constant_count = len(constant_columns)
    expected_quality = 100.0
    expected_quality -= min(35, total_missing / max(total_cells, 1) * 100 * 0.8)
    expected_quality -= min(20, duplicate_copies / max(rows, 1) * 100)
    expected_quality -= min(15, constant_count / max(columns, 1) * 100 * 0.5)
    expected_quality = round(max(0.0, expected_quality), 2)
    if (
        isinstance(quality_score, bool)
        or not isinstance(quality_score, (int, float))
        or not math.isclose(float(quality_score), expected_quality, abs_tol=1e-9)
    ):
        errors.append({"code": "invalid_profile_quality_score", "message": str(quality_score)})

    count_prefix = "profile.quality.missing.column."
    pct_prefix = "profile.quality.missing_pct.column."
    counts = {
        finding_id.removeprefix(count_prefix): finding
        for finding_id, finding in finding_index.items()
        if finding_id.startswith(count_prefix)
    }
    percentages = {
        finding_id.removeprefix(pct_prefix): finding
        for finding_id, finding in finding_index.items()
        if finding_id.startswith(pct_prefix)
    }
    allowed_ids = (
        _PROFILE_REQUIRED_FINDINGS
        | {finding["finding_id"] for finding in counts.values()}
        | {finding["finding_id"] for finding in percentages.values()}
    )
    unsupported = sorted(set(finding_index) - allowed_ids)
    if unsupported:
        errors.append({"code": "unsupported_profile_finding", "message": ", ".join(unsupported)})
    if set(counts) != set(percentages):
        errors.append({"code": "profile_missing_pair_mismatch", "message": "column indexes"})
    valid_missing_sum = 0
    for suffix in sorted(set(counts) & set(percentages)):
        count_finding = counts[suffix]
        pct_finding = percentages[suffix]
        count = count_finding.get("value")
        pct = pct_finding.get("value")
        same_dimension = count_finding.get("dimension") == pct_finding.get("dimension")
        valid_count = isinstance(count, int) and not isinstance(count, bool) and 0 < count <= rows
        valid_pct = isinstance(pct, (int, float)) and not isinstance(pct, bool)
        expected_pct = round(count / max(rows, 1) * 100, 2) if valid_count else None
        if (
            not valid_count
            or not valid_pct
            or not math.isclose(float(pct), float(expected_pct), abs_tol=1e-9)
            or not same_dimension
            or count_finding.get("unit") != "cells"
            or count_finding.get("source") != "dataframe_isna_sum"
            or pct_finding.get("unit") != "percent_of_column_rows"
            or pct_finding.get("source") != "column_isna_mean"
        ):
            errors.append({"code": "invalid_profile_column_missing", "message": suffix})
        else:
            valid_missing_sum += count
    if valid_missing_sum != total_missing:
        errors.append({"code": "profile_missing_sum_mismatch", "message": str(valid_missing_sum)})
    return errors


def verify_tool_result(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    errors = _verify_findings(result.get("findings"))
    forbidden = sorted(_forbidden_keys(result))
    if forbidden:
        errors.append({"code": "raw_or_unbounded_result", "message": ", ".join(forbidden)})
    finding_ids = {
        finding.get("finding_id")
        for finding in result.get("findings", [])
        if isinstance(finding, dict)
    }
    if tool == "profile_dataset":
        missing = sorted(_PROFILE_REQUIRED_FINDINGS - finding_ids)
        if result.get("schema_version") != "profile-evidence.v1":
            errors.append({"code": "invalid_profile_contract", "message": "schema_version"})
        if missing:
            errors.append({"code": "missing_profile_findings", "message": ", ".join(missing)})
        errors.extend(_verify_profile_result(result))
    elif tool == "screen_target_associations":
        if set(result) != _ANALYST_RESULT_KEYS:
            errors.append({"code": "invalid_analyst_contract", "message": "top-level keys"})
        if result.get("schema_version") != "analyst.v1":
            errors.append({"code": "invalid_analyst_contract", "message": "schema_version"})
        recomputed = verify_analyst_payload(result)
        if recomputed["status"] != "passed":
            errors.append(
                {
                    "code": "analyst_verification_failed",
                    "message": ", ".join(sorted({error["code"] for error in recomputed["errors"]})),
                }
            )
        semantics = result.get("target_semantics", {})
        if (
            semantics.get("selection_source") != "explicit_request"
            or semantics.get("business_meaning_status") != "unverified"
            or semantics.get("business_meaning") is not None
        ):
            errors.append({"code": "unsupported_business_semantics", "message": "target"})
        kpis = result.get("kpi_selection", {})
        if kpis.get("status") != "requires_approved_definition" or kpis.get("selected"):
            errors.append({"code": "unsupported_kpi_selection", "message": "kpi"})
    else:
        errors.append({"code": "tool_not_allowlisted", "message": tool})
    return {
        "status": "passed" if not errors else "failed",
        "scope": "typed_tool_numeric_evidence_and_semantics",
        "errors": errors,
    }


def _criterion_for(step: InvestigateStep) -> CompletionCriterion:
    return "profile_verified" if isinstance(step, ProfileStep) else "target_screen_verified"


def _select_synthesis_evidence(
    events: list[dict[str, Any]],
    evidence_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_ids: list[str] = []

    def select(finding_id: Any) -> None:
        if (
            isinstance(finding_id, str)
            and finding_id in evidence_index
            and finding_id not in selected_ids
            and len(selected_ids) < _MAX_SYNTHESIS_FINDINGS
        ):
            selected_ids.append(finding_id)

    for finding_id in _PROFILE_CORE_SPECS:
        select(finding_id)

    profile_missing_counts = [
        finding
        for finding in evidence_index.values()
        if finding["finding_id"].startswith("profile.quality.missing.column.")
    ]
    profile_missing_counts.sort(key=lambda finding: (-finding["value"], finding["finding_id"]))
    for finding in profile_missing_counts[:10]:
        finding_id = finding["finding_id"]
        select(finding_id)
        select(finding_id.replace(".missing.column.", ".missing_pct.column."))

    for event in events:
        if event.get("status") != "completed" or event.get("tool") != "screen_target_associations":
            continue
        result = event.get("result", {})
        analyses_by_effect = {
            analysis.get("finding_ids", {}).get("effect"): analysis
            for analysis in result.get("analyses", [])
            if isinstance(analysis, dict)
        }
        for card in result.get("dashboard", {}).get("cards", [])[:5]:
            analysis = analyses_by_effect.get(card.get("finding_id"))
            if not isinstance(analysis, dict):
                continue
            for role in ("effect", "p_value", "adjusted_p_value", "n"):
                select(analysis.get("finding_ids", {}).get(role))

    if not selected_ids:
        for finding_id in sorted(evidence_index):
            select(finding_id)
    return [evidence_index[finding_id] for finding_id in selected_ids]


class BoundedInvestigateExecutor:
    def __init__(
        self,
        *,
        budget: ExecutionBudget | None = None,
        registry: dict[str, ToolHandler] | None = None,
    ) -> None:
        self.budget = budget or ExecutionBudget()
        self.registry = dict(DEFAULT_TOOL_REGISTRY if registry is None else registry)
        unknown = sorted(set(self.registry) - set(DEFAULT_TOOL_REGISTRY))
        if unknown:
            raise ValueError(f"allowlist dışı registry aracı: {unknown}")

    def run(self, plan: InvestigatePlan) -> dict[str, Any]:
        settings = get_settings()
        dataset_path = resolve_workspace_path(settings.workspace, plan.dataset_ref)
        if not dataset_path.is_file():
            raise FileNotFoundError(dataset_path)

        events: list[dict[str, Any]] = []
        signatures: set[str] = set()
        completed_steps: set[str] = set()
        completed_criteria: set[CompletionCriterion] = set()
        failures = 0
        stop_reason: str | None = None

        for step in plan.steps[: self.budget.max_steps]:
            if set(plan.completion_criteria) <= completed_criteria:
                stop_reason = "goal_completed"
                break
            if not set(step.depends_on) <= completed_steps:
                failures += 1
                events.append(
                    {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "status": "failed",
                        "error": {"code": "dependency_failed"},
                    }
                )
                if failures >= self.budget.max_failed_calls:
                    stop_reason = "failure_budget_exhausted"
                    break
                continue

            signature = json.dumps(
                {"tool": step.tool, "arguments": step.arguments.model_dump(mode="json")},
                sort_keys=True,
                separators=(",", ":"),
            )
            if signature in signatures:
                events.append(
                    {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "status": "failed",
                        "error": {"code": "duplicate_tool_call"},
                    }
                )
                stop_reason = "duplicate_tool_call"
                break
            signatures.add(signature)

            handler = self.registry.get(step.tool)
            if handler is None:
                events.append(
                    {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "status": "failed",
                        "error": {"code": "tool_not_allowlisted"},
                    }
                )
                stop_reason = "tool_not_allowlisted"
                break
            try:
                result = handler(plan, step)
                verification = verify_tool_result(step.tool, result)
            except Exception as exc:
                failures += 1
                events.append(
                    {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "status": "failed",
                        "error": {"code": "tool_failed", "type": type(exc).__name__},
                    }
                )
                if failures >= self.budget.max_failed_calls:
                    stop_reason = "failure_budget_exhausted"
                    break
                continue

            if verification["status"] != "passed":
                failures += 1
                events.append(
                    {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "status": "failed",
                        "verification": verification,
                    }
                )
                if failures >= self.budget.max_failed_calls:
                    stop_reason = "failure_budget_exhausted"
                    break
                continue

            events.append(
                {
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "status": "completed",
                    "verification": verification,
                    "result": result,
                }
            )
            completed_steps.add(step.step_id)
            completed_criteria.add(_criterion_for(step))

        goals_met = set(plan.completion_criteria) <= completed_criteria
        if goals_met and stop_reason is None:
            stop_reason = "goal_completed"
        elif not goals_met and stop_reason is None:
            stop_reason = "plan_exhausted_before_goal"

        evidence_index: dict[str, dict[str, Any]] = {}
        for event in events:
            if event["status"] != "completed":
                continue
            for finding in event["result"]["findings"]:
                evidence_index[finding["finding_id"]] = finding
        evidence = [evidence_index[finding_id] for finding_id in sorted(evidence_index)]
        synthesis_evidence = _select_synthesis_evidence(events, evidence_index)

        run: dict[str, Any] = {
            "schema_version": "investigate-run.v1",
            "status": "completed" if goals_met else "stopped",
            "stop_reason": stop_reason,
            "completion": {
                "required": plan.completion_criteria,
                "completed": sorted(completed_criteria),
            },
            "budget": {
                "max_steps": self.budget.max_steps,
                "max_failed_calls": self.budget.max_failed_calls,
                "failed_calls": failures,
            },
            "events": events,
            "evidence": evidence,
        }
        run["verification"] = verify_investigate_run(run)
        synthesis_blocked = run["verification"]["status"] != "passed"
        run["synthesis_request"] = {
            "mode": "tool_less",
            "status": "blocked" if synthesis_blocked else "ready",
            "objective": plan.objective,
            "run_status": run["status"],
            "evidence": [] if synthesis_blocked else synthesis_evidence,
            "evidence_scope": {
                "verified_total": len(evidence),
                "included": 0 if synthesis_blocked else len(synthesis_evidence),
                "maximum": _MAX_SYNTHESIS_FINDINGS,
            },
            "rules": [
                "Use only supplied evidence values and cite finding_id for every numeric claim.",
                "Association is not causality or business importance.",
                "Do not invent KPI, benchmark, prediction meaning, threshold, or company rule.",
                "If evidence is insufficient, say what cannot be determined.",
            ],
        }
        return run


def verify_investigate_run(run: dict[str, Any]) -> dict[str, Any]:
    evidence = run.get("evidence")
    errors = _verify_findings(evidence)
    evidence_index: dict[str, dict[str, Any]] = {}
    if isinstance(evidence, list):
        for finding in evidence:
            if not isinstance(finding, dict):
                continue
            finding_id = finding.get("finding_id")
            if isinstance(finding_id, str) and finding_id:
                if finding_id in evidence_index:
                    errors.append({"code": "duplicate_run_evidence", "message": finding_id})
                evidence_index[finding_id] = finding

    event_evidence: dict[str, dict[str, Any]] = {}
    for event in run.get("events", []):
        if (
            event.get("status") == "completed"
            and event.get("verification", {}).get("status") != "passed"
        ):
            errors.append(
                {"code": "unverified_completed_step", "message": str(event.get("step_id"))}
            )
        if event.get("status") == "completed":
            result = event.get("result")
            if not isinstance(result, dict):
                errors.append(
                    {"code": "invalid_completed_step_result", "message": str(event.get("step_id"))}
                )
                continue
            recomputed = verify_tool_result(str(event.get("tool")), result)
            if recomputed["status"] != "passed":
                errors.append(
                    {
                        "code": "completed_step_reverification_failed",
                        "message": str(event.get("step_id")),
                    }
                )
            for finding in result.get("findings", []):
                if not isinstance(finding, dict):
                    continue
                finding_id = finding.get("finding_id")
                if not isinstance(finding_id, str) or not finding_id:
                    continue
                existing = event_evidence.get(finding_id)
                if existing is not None and existing != finding:
                    errors.append({"code": "conflicting_step_evidence", "message": finding_id})
                else:
                    event_evidence[finding_id] = finding

    if set(evidence_index) != set(event_evidence):
        errors.append({"code": "run_evidence_chain_mismatch", "message": "finding_id set"})
    for finding_id in sorted(set(evidence_index) & set(event_evidence)):
        if evidence_index[finding_id] != event_evidence[finding_id]:
            errors.append({"code": "run_evidence_value_mismatch", "message": finding_id})
    return {
        "status": "passed" if not errors else "failed",
        "scope": "bounded_steps_verified_numeric_evidence_no_raw_rows",
        "errors": errors,
    }
