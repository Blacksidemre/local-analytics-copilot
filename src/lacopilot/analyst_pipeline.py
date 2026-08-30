from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats

from lacopilot.analyst_interpretation import interpret_analyst_payload
from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table, serializable
from lacopilot.tools.data_tools import profile_dataset

TargetKind = Literal["binary", "continuous", "categorical"]

_MAX_PREDICTORS = 50
_DEFAULT_PREDICTOR_ROLES = {"numeric", "categorical", "boolean"}


def _sheet_arg(sheet_name: str) -> str | int:
    return int(sheet_name) if str(sheet_name).isdigit() else sheet_name


def _load(file_path: str, sheet_name: str) -> pd.DataFrame:
    settings = get_settings()
    path = resolve_workspace_path(settings.workspace, file_path)
    return load_table(path, _sheet_arg(sheet_name))


def _ordered_unique(series: pd.Series) -> list[Any]:
    return sorted(pd.unique(series.dropna()).tolist(), key=lambda value: str(value))


def _resolve_target_kind(series: pd.Series, requested: TargetKind | None) -> TargetKind:
    unique = _ordered_unique(series)
    if len(unique) < 2:
        raise ValueError("Hedef sütun en az iki gözlenen sınıf/değer içermeli")
    if requested == "binary":
        if len(unique) != 2:
            raise ValueError("Binary hedef tam olarak iki gözlenen sınıf içermeli")
        return "binary"
    if requested == "continuous":
        if not pd.api.types.is_numeric_dtype(series) or len(unique) < 3:
            raise ValueError("Continuous hedef numeric ve en az üç farklı değer içermeli")
        return "continuous"
    if requested == "categorical":
        if len(unique) > 50:
            raise ValueError("Categorical hedef en fazla 50 sınıf içerebilir")
        return "categorical"
    if len(unique) == 2:
        return "binary"
    raise ValueError(
        "Hedefin business anlamı sütun adından çıkarılamaz; target_kind açıkça belirtilmeli"
    )


def _role_by_column(profile: dict[str, Any]) -> dict[str, str]:
    return {
        str(column): role
        for role, columns in profile.get("roles", {}).items()
        for column in columns
    }


def _select_predictors(
    frame: pd.DataFrame,
    profile: dict[str, Any],
    target_column: str,
    requested: list[str] | None,
) -> tuple[list[str], str]:
    role_map = _role_by_column(profile)
    if requested is None:
        predictors = [
            str(column)
            for column in frame.columns
            if str(column) != target_column
            and role_map.get(str(column)) in _DEFAULT_PREDICTOR_ROLES
            and frame[column].nunique(dropna=True) > 1
        ]
        source = "deterministic_role_filter"
    else:
        if len(requested) != len(set(requested)):
            raise ValueError("predictor_columns tekrar eden sütun içeremez")
        missing = [column for column in requested if column not in frame.columns]
        if missing:
            raise ValueError(f"Predictor sütunları bulunamadı: {missing}")
        if target_column in requested:
            raise ValueError("Hedef sütun predictor olarak kullanılamaz")
        unsupported = [
            column for column in requested if role_map.get(column) not in _DEFAULT_PREDICTOR_ROLES
        ]
        if unsupported:
            raise ValueError(
                "Identifier, datetime veya serbest metin sütunları otomatik association "
                f"taramasına alınamaz: {unsupported}"
            )
        predictors = list(requested)
        source = "explicit_request"
    if not predictors:
        raise ValueError("İstatistiksel tarama için uygun predictor bulunamadı")
    if len(predictors) > _MAX_PREDICTORS:
        raise ValueError(
            f"En fazla {_MAX_PREDICTORS} predictor taranabilir; predictor_columns ile daraltın"
        )
    return predictors, source


def _predictor_kind(series: pd.Series) -> Literal["numeric", "categorical"]:
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return "numeric"
    unique = int(series.nunique(dropna=True))
    if 2 <= unique <= 50:
        return "categorical"
    raise ValueError("Predictor numeric veya en fazla 50 seviyeli categorical olmalı")


def _rank_biserial(u_statistic: float, n_a: int, n_b: int) -> float:
    return float(1 - (2 * u_statistic) / (n_a * n_b))


def _cramers_v(table: pd.DataFrame, chi_square: float) -> float:
    observations = int(table.to_numpy().sum())
    denominator = observations * max(min(table.shape) - 1, 0)
    return math.sqrt(chi_square / denominator) if denominator else 0.0


def _screen_contingency(target: pd.Series, predictor: pd.Series) -> dict[str, Any] | None:
    table = pd.crosstab(target, predictor)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return None
    chi_square, p_value, _, expected = stats.chi2_contingency(table)
    method = "chi_square"
    p_source = "scipy_chi2_contingency"
    assumption_status = "passed" if bool((expected >= 5).all()) else "warning"
    warning = (
        "Bazı beklenen hücre frekansları 5'in altında; sonuç ihtiyatla yorumlanmalı."
        if assumption_status == "warning"
        else None
    )
    if table.shape == (2, 2) and assumption_status == "warning":
        _, p_value = stats.fisher_exact(table.to_numpy())
        method = "fisher_exact"
        p_source = "scipy_fisher_exact"
    return {
        "method": method,
        "effect_name": "cramers_v",
        "effect": _cramers_v(table, float(chi_square)),
        "effect_source": "cramers_v_from_chi_square",
        "p_value": float(p_value),
        "p_source": p_source,
        "n": int(table.to_numpy().sum()),
        "assumption_status": assumption_status,
        "warning": warning,
    }


def _screen_grouped_numeric(numeric: pd.Series, grouping: pd.Series) -> dict[str, Any] | None:
    work = pd.DataFrame({"numeric": pd.to_numeric(numeric, errors="coerce"), "group": grouping})
    work = work.dropna()
    labels = _ordered_unique(work["group"])
    arrays = [work.loc[work["group"].eq(label), "numeric"].to_numpy(float) for label in labels]
    if len(arrays) < 2 or any(len(values) < 3 for values in arrays):
        return None
    if len(arrays) == 2:
        result = stats.mannwhitneyu(arrays[0], arrays[1], alternative="two-sided")
        effect = _rank_biserial(float(result.statistic), len(arrays[0]), len(arrays[1]))
        method = "mann_whitney_u"
        effect_name = "rank_biserial"
        effect_source = "rank_biserial_from_mann_whitney_u"
        p_source = "scipy_mannwhitneyu"
    else:
        result = stats.kruskal(*arrays)
        total = sum(len(values) for values in arrays)
        effect = max(
            0.0,
            (float(result.statistic) - len(arrays) + 1) / max(total - len(arrays), 1),
        )
        method = "kruskal_wallis"
        effect_name = "epsilon_squared"
        effect_source = "epsilon_squared_from_kruskal_wallis"
        p_source = "scipy_kruskal"
    return {
        "method": method,
        "effect_name": effect_name,
        "effect": float(effect),
        "effect_source": effect_source,
        "p_value": float(result.pvalue),
        "p_source": p_source,
        "n": int(sum(len(values) for values in arrays)),
        "assumption_status": "passed",
        "warning": "Association does not establish causality.",
        "class_order": [serializable(label) for label in labels],
    }


def _screen_spearman(target: pd.Series, predictor: pd.Series) -> dict[str, Any] | None:
    work = pd.DataFrame(
        {
            "target": pd.to_numeric(target, errors="coerce"),
            "predictor": pd.to_numeric(predictor, errors="coerce"),
        }
    ).dropna()
    if len(work) < 3 or work["target"].nunique() < 2 or work["predictor"].nunique() < 2:
        return None
    result = stats.spearmanr(work["target"], work["predictor"])
    if not np.isfinite(result.statistic) or not np.isfinite(result.pvalue):
        return None
    return {
        "method": "spearman",
        "effect_name": "spearman_r",
        "effect": float(result.statistic),
        "effect_source": "scipy_spearmanr",
        "p_value": float(result.pvalue),
        "p_source": "scipy_spearmanr",
        "n": int(len(work)),
        "assumption_status": "passed",
        "warning": "Correlation does not establish causality.",
    }


def _screen_predictor(
    frame: pd.DataFrame,
    target_column: str,
    target_kind: TargetKind,
    predictor: str,
) -> dict[str, Any] | None:
    target = frame[target_column]
    candidate = frame[predictor]
    predictor_kind = _predictor_kind(candidate)
    if target_kind == "continuous" and predictor_kind == "numeric":
        result = _screen_spearman(target, candidate)
    elif target_kind == "continuous":
        result = _screen_grouped_numeric(target, candidate)
    elif predictor_kind == "numeric":
        result = _screen_grouped_numeric(candidate, target)
    else:
        result = _screen_contingency(target, candidate)
    if result is not None:
        result["predictor_kind"] = predictor_kind
    return result


def _benjamini_hochberg(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    count = len(p_values)
    order = sorted(range(count), key=p_values.__getitem__)
    adjusted = [1.0] * count
    running = 1.0
    for rank_index in range(count - 1, -1, -1):
        original_index = order[rank_index]
        rank = rank_index + 1
        running = min(running, p_values[original_index] * count / rank)
        adjusted[original_index] = min(1.0, max(p_values[original_index], running))
    return adjusted


def _metric_finding(
    finding_id: str,
    label: str,
    value: float | int,
    unit: str,
    source: str,
    target: str,
    predictor: str,
    method: str,
    warning: str | None = None,
) -> dict[str, Any]:
    finding = {
        "finding_id": finding_id,
        "kind": "statistical_metric",
        "label": label,
        "value": value,
        "unit": unit,
        "source": source,
        "dimension": {"target": target, "predictor": predictor, "method": method},
    }
    if warning:
        finding["warning"] = warning
    return finding


def _materialize_findings(
    results: list[dict[str, Any]], target_column: str, target_index: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    adjusted = _benjamini_hochberg([result["p_value"] for result in results])
    findings: list[dict[str, Any]] = []
    analyses: list[dict[str, Any]] = []
    for result, adjusted_p in zip(results, adjusted, strict=True):
        predictor = result["predictor"]
        base = f"analyst.target.{target_index}.association.column.{result['predictor_index']}"
        ids = {
            "effect": f"{base}.effect",
            "p_value": f"{base}.p_value",
            "adjusted_p_value": f"{base}.adjusted_p_value",
            "n": f"{base}.n",
        }
        findings.extend(
            [
                _metric_finding(
                    ids["effect"],
                    f"{predictor} association effect",
                    result["effect"],
                    result["effect_name"],
                    result["effect_source"],
                    target_column,
                    predictor,
                    result["method"],
                    result.get("warning"),
                ),
                _metric_finding(
                    ids["p_value"],
                    f"{predictor} raw p-value",
                    result["p_value"],
                    "p_value",
                    result["p_source"],
                    target_column,
                    predictor,
                    result["method"],
                ),
                _metric_finding(
                    ids["adjusted_p_value"],
                    f"{predictor} adjusted p-value",
                    adjusted_p,
                    "adjusted_p_value",
                    "benjamini_hochberg_all_executed_tests",
                    target_column,
                    predictor,
                    result["method"],
                ),
                _metric_finding(
                    ids["n"],
                    f"{predictor} complete observations",
                    result["n"],
                    "observations",
                    "pairwise_complete_observation_count",
                    target_column,
                    predictor,
                    result["method"],
                ),
            ]
        )
        analysis = {
            "analysis_id": base,
            "target": target_column,
            "predictor": predictor,
            "predictor_kind": result["predictor_kind"],
            "method": result["method"],
            "effect_name": result["effect_name"],
            "finding_ids": ids,
            "assumption_status": result["assumption_status"],
        }
        if result.get("class_order") is not None:
            analysis["class_order"] = result["class_order"]
        if result.get("warning"):
            analysis["warning"] = result["warning"]
        analyses.append(analysis)
    return findings, analyses


def _build_dashboard(findings: list[dict[str, Any]]) -> dict[str, Any]:
    finding_index = {finding["finding_id"]: finding for finding in findings}
    effects = [finding for finding in findings if finding["finding_id"].endswith(".effect")]
    effects.sort(
        key=lambda finding: (
            finding_index[f"{finding['finding_id'][:-7]}.adjusted_p_value"]["value"],
            finding["finding_id"],
        )
    )
    cards = [dict(finding) for finding in effects[:5]]
    return {
        "schema_version": 1,
        "title": "Deterministic target association screening",
        "cards": cards,
        "ranking_basis": "adjusted_p_value_then_finding_id",
        "evidence_policy": "all_numeric_cards_bound_to_finding_id",
        "warning": "Cards prioritize smaller adjusted p-values for screening; they do not rank business importance, causality, or approved KPIs.",
    }


def verify_analyst_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    findings = payload.get("findings", [])
    finding_index: dict[str, dict[str, Any]] = {}
    for finding in findings:
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            errors.append({"code": "invalid_finding_id", "message": "Finding ID missing"})
            continue
        if finding_id in finding_index:
            errors.append({"code": "duplicate_finding_id", "message": finding_id})
        finding_index[finding_id] = finding
        value = finding.get("value")
        valid_numeric = (
            not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
        )
        if not valid_numeric:
            errors.append({"code": "invalid_numeric_value", "message": finding_id})
            continue
        if finding.get("unit") in {"p_value", "adjusted_p_value"} and not 0 <= value <= 1:
            errors.append({"code": "invalid_probability_range", "message": finding_id})
        if not finding.get("source"):
            errors.append({"code": "missing_source", "message": finding_id})

    analysis_ids: set[str] = set()
    for analysis in payload.get("analyses", []):
        analysis_id = analysis.get("analysis_id")
        if analysis_id in analysis_ids:
            errors.append({"code": "duplicate_analysis_id", "message": str(analysis_id)})
        analysis_ids.add(str(analysis_id))
        references = analysis.get("finding_ids", {})
        if not isinstance(references, dict) or set(references) != {
            "effect",
            "p_value",
            "adjusted_p_value",
            "n",
        }:
            errors.append({"code": "invalid_finding_reference_set", "message": str(analysis_id)})
            continue
        if any(finding_id not in finding_index for finding_id in references.values()):
            errors.append({"code": "unknown_finding_reference", "message": str(analysis_id)})
            continue
        raw_p = finding_index[references["p_value"]]["value"]
        adjusted_p = finding_index[references["adjusted_p_value"]]["value"]
        if adjusted_p < raw_p:
            errors.append({"code": "invalid_multiple_test_adjustment", "message": str(analysis_id)})

    card_ids: set[str] = set()
    for card in payload.get("dashboard", {}).get("cards", []):
        card_id = card.get("finding_id")
        if card_id in card_ids:
            errors.append({"code": "duplicate_dashboard_card", "message": str(card_id)})
        card_ids.add(str(card_id))
        finding = finding_index.get(card.get("finding_id"))
        if (
            finding is None
            or card.get("value") != finding.get("value")
            or card.get("source") != finding.get("source")
        ):
            errors.append(
                {"code": "unbound_dashboard_card", "message": str(card.get("finding_id"))}
            )

    semantics = payload.get("target_semantics", {})
    if semantics.get("selection_source") != "explicit_request":
        errors.append({"code": "target_not_explicit", "message": "Target must be user-selected"})
    if semantics.get("business_meaning_status") != "unverified":
        errors.append(
            {
                "code": "unsupported_business_semantics",
                "message": "Business meaning must be unverified",
            }
        )
    kpis = payload.get("kpi_selection", {})
    if kpis.get("status") != "requires_approved_definition" or kpis.get("selected"):
        errors.append({"code": "unsupported_kpi_selection", "message": "No approved KPI supplied"})

    return {
        "status": "passed" if not errors else "failed",
        "scope": "finding_references_numeric_sources_multiple_testing_and_semantics",
        "errors": errors,
    }


def run_analyst_pipeline(
    file_path: str,
    target_column: str,
    sheet_name: str = "0",
    target_kind: TargetKind | None = None,
    predictor_columns: list[str] | None = None,
    interpret: bool = False,
    question: str = "",
    language: str = "tr",
    model: str | None = None,
) -> dict[str, Any]:
    """Run a bounded deterministic target-association screen without inferring business meaning."""
    profile = profile_dataset(file_path, sheet_name)
    frame = _load(file_path, sheet_name)
    if target_column not in frame.columns:
        raise ValueError(f"Hedef sütun bulunamadı: {target_column}")
    resolved_target_kind = _resolve_target_kind(frame[target_column], target_kind)
    predictors, predictor_source = _select_predictors(
        frame, profile, target_column, predictor_columns
    )
    column_indexes = {str(column): index for index, column in enumerate(frame.columns)}
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for predictor in predictors:
        try:
            result = _screen_predictor(frame, target_column, resolved_target_kind, predictor)
        except (TypeError, ValueError) as exc:
            skipped.append({"predictor": predictor, "reason": str(exc)})
            continue
        if result is None:
            skipped.append(
                {"predictor": predictor, "reason": "insufficient_complete_or_variable_data"}
            )
            continue
        result["predictor"] = predictor
        result["predictor_index"] = column_indexes[predictor]
        results.append(result)
    if not results:
        raise ValueError("Seçilen predictorlar için çalıştırılabilir association testi bulunamadı")

    findings, analyses = _materialize_findings(
        results, target_column, column_indexes[target_column]
    )
    payload: dict[str, Any] = {
        "schema_version": "analyst.v1",
        "status": "completed",
        "mode": "analyst",
        "file_path": file_path,
        "selected_sheet": sheet_name,
        "profile": profile,
        "target_semantics": {
            "column": target_column,
            "statistical_role": resolved_target_kind,
            "selection_source": "explicit_request",
            "business_meaning_status": "unverified",
            "business_meaning": None,
        },
        "kpi_selection": {
            "status": "requires_approved_definition",
            "selected": [],
            "reason": "Column names and data shape do not prove an approved business KPI definition.",
        },
        "predictor_selection": {
            "source": predictor_source,
            "included": predictors,
            "skipped": skipped,
        },
        "multiple_testing": {
            "method": "benjamini_hochberg",
            "family": "all_executed_target_association_tests",
        },
        "analyses": analyses,
        "findings": findings,
        "dashboard": _build_dashboard(findings),
        "interpretation": {
            "status": "skipped",
        },
    }
    payload["verification"] = verify_analyst_payload(payload)
    if payload["verification"]["status"] != "passed":
        raise RuntimeError("Analyst payload deterministic verification failed")
    if interpret:
        payload["interpretation"] = interpret_analyst_payload(
            payload,
            question=question,
            language=language,
            model=model,
        )
    settings = get_settings()
    audit(
        settings.logs_dir,
        "analyst_pipeline",
        file=file_path,
        target=target_column,
        target_kind=resolved_target_kind,
        predictors=predictors,
    )
    return payload
