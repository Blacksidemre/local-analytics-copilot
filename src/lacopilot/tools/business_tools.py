from __future__ import annotations

import json

import numpy as np
import pandas as pd

from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table


def _load(file_path: str, sheet_name: str = "0") -> pd.DataFrame:
    s = get_settings()
    p = resolve_workspace_path(s.workspace, file_path)
    sh = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    return load_table(p, sh)


def pareto_abc(
    file_path: str, entity_column: str, value_column: str, sheet_name: str = "0"
) -> dict:
    """Pareto/ABC contribution segmentation using cumulative value share.

    A <=80%, B <=95%, C remainder. Thresholds are conventional defaults and can be adapted to business policy.
    """
    df = _load(file_path, sheet_name)
    work = df[[entity_column, value_column]].copy()
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce").fillna(0)
    if (work[value_column] < 0).any():
        raise ValueError("Pareto/ABC için value_column negatif değer içermemeli")
    g = work.groupby(entity_column, dropna=False)[value_column].sum().sort_values(ascending=False)
    total = float(g.sum())
    out = g.reset_index(name="value")
    out["share_pct"] = np.where(total, out["value"] / total * 100, 0)
    out["cum_share_pct"] = out["share_pct"].cumsum()
    out["abc"] = np.select(
        [out["cum_share_pct"] <= 80, out["cum_share_pct"] <= 95], ["A", "B"], default="C"
    )
    return {
        "total": total,
        "entities": len(out),
        "summary": out.groupby("abc")
        .agg(entity_count=(entity_column, "count"), value=("value", "sum"))
        .reset_index()
        .to_dict(orient="records"),
        "top_entities": out.head(50).to_dict(orient="records"),
    }


def contribution_analysis(
    file_path: str,
    group_column: str,
    value_column: str,
    comparison_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Group contribution analysis; optionally compare a second numeric measure and calculate variance contribution."""
    df = _load(file_path, sheet_name)
    cols = [group_column, value_column] + ([comparison_column] if comparison_column else [])
    work = df[cols].copy()
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce").fillna(0)
    agg = work.groupby(group_column, dropna=False)[value_column].sum().reset_index()
    total = float(agg[value_column].sum())
    agg["contribution_pct"] = np.where(total, agg[value_column] / total * 100, 0)
    if comparison_column:
        work[comparison_column] = pd.to_numeric(work[comparison_column], errors="coerce").fillna(0)
        comp = work.groupby(group_column, dropna=False)[comparison_column].sum().reset_index()
        agg = agg.merge(comp, on=group_column, how="left")
        agg["variance"] = agg[value_column] - agg[comparison_column]
        denom = float(np.abs(agg["variance"]).sum())
        agg["abs_variance_contribution_pct"] = np.where(
            denom, np.abs(agg["variance"]) / denom * 100, 0
        )
    return {
        "rows": agg.sort_values(value_column, ascending=False).to_dict(orient="records"),
        "total": total,
    }


def funnel_analysis(file_path: str, stages: list[str], sheet_name: str = "0") -> dict:
    """Compute funnel counts from boolean/0-1 stage columns. Stages should be ordered from broadest to narrowest."""
    df = _load(file_path, sheet_name)
    missing = [c for c in stages if c not in df]
    if missing:
        raise KeyError(f"Kolonlar bulunamadı: {missing}")
    rows = []
    prev = None
    for c in stages:
        x = df[c]
        if pd.api.types.is_bool_dtype(x):
            count = int(x.fillna(False).sum())
        else:
            n = pd.to_numeric(x, errors="coerce")
            if n.notna().mean() > 0.8:
                count = int((n.fillna(0) > 0).sum())
            else:
                count = int(
                    x.astype("string")
                    .str.lower()
                    .isin(["true", "yes", "evet", "1", "completed", "success"])
                    .sum()
                )
        conv = 100.0 if prev is None else (count / prev * 100 if prev > 0 else None)
        rows.append({"stage": c, "count": count, "conversion_from_previous_pct": conv})
        prev = count
    return {
        "stages": rows,
        "guardrail": "Stage columns must represent a logically nested funnel; verify that later stages are subsets of earlier stages.",
    }


def cohort_analysis(
    file_path: str,
    entity_column: str,
    start_date_column: str,
    activity_date_column: str,
    value_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Generic monthly cohort analysis by entity start month and months-since-start activity."""
    df = _load(file_path, sheet_name)
    cols = [entity_column, start_date_column, activity_date_column] + (
        [value_column] if value_column else []
    )
    work = df[cols].copy()
    work[start_date_column] = pd.to_datetime(work[start_date_column], errors="coerce")
    work[activity_date_column] = pd.to_datetime(work[activity_date_column], errors="coerce")
    work = work.dropna(subset=[entity_column, start_date_column, activity_date_column])
    work["cohort"] = work[start_date_column].dt.to_period("M").astype(str)
    work["period_index"] = (
        work[activity_date_column].dt.year - work[start_date_column].dt.year
    ) * 12 + (work[activity_date_column].dt.month - work[start_date_column].dt.month)
    work = work[work.period_index >= 0]
    if value_column:
        work[value_column] = pd.to_numeric(work[value_column], errors="coerce").fillna(0)
        tab = work.groupby(["cohort", "period_index"])[value_column].sum().reset_index(name="value")
    else:
        tab = (
            work.groupby(["cohort", "period_index"])[entity_column]
            .nunique()
            .reset_index(name="value")
        )
    return {
        "rows": tab.head(10000).to_dict(orient="records"),
        "metric": "sum" if value_column else "active_entities",
    }


def rfm_segmentation(
    file_path: str,
    customer_column: str,
    date_column: str,
    amount_column: str,
    reference_date: str = "",
    sheet_name: str = "0",
) -> dict:
    """RFM segmentation for transaction-style data. Intended as generic business segmentation, not an NPL credit decision model."""
    df = _load(file_path, sheet_name)
    work = df[[customer_column, date_column, amount_column]].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work[amount_column] = pd.to_numeric(work[amount_column], errors="coerce")
    work = work.dropna()
    if work.empty:
        raise ValueError("RFM için geçerli müşteri/tarih/tutar satırı bulunamadı")
    ref = (
        pd.Timestamp(reference_date)
        if reference_date
        else work[date_column].max() + pd.Timedelta(days=1)
    )
    rfm = (
        work.groupby(customer_column)
        .agg(
            recency=(date_column, lambda x: (ref - x.max()).days),
            frequency=(date_column, "count"),
            monetary=(amount_column, "sum"),
        )
        .reset_index()
    )

    def score(series, reverse=False):
        ranked = series.rank(method="first", pct=True)
        q = np.ceil(ranked * 5).clip(1, 5).astype(int)
        return (6 - q) if reverse else q

    rfm["R"] = score(rfm.recency, reverse=True)
    rfm["F"] = score(rfm.frequency)
    rfm["M"] = score(rfm.monetary)
    rfm["rfm_score"] = rfm.R.astype(str) + rfm.F.astype(str) + rfm.M.astype(str)
    return {
        "reference_date": str(ref.date()),
        "customers": len(rfm),
        "top": rfm.sort_values(["R", "F", "M"], ascending=False).head(50).to_dict(orient="records"),
    }


def break_even_analysis(
    fixed_cost: float,
    price_per_unit: float,
    variable_cost_per_unit: float,
    target_profit: float = 0.0,
) -> dict:
    """Simple deterministic break-even/target-profit analysis."""
    margin = price_per_unit - variable_cost_per_unit
    if margin <= 0:
        raise ValueError("Contribution margin pozitif olmalı")
    units = (fixed_cost + target_profit) / margin
    revenue = units * price_per_unit
    return {
        "contribution_margin_per_unit": margin,
        "contribution_margin_pct": margin / price_per_unit * 100 if price_per_unit else None,
        "required_units": units,
        "required_revenue": revenue,
        "target_profit": target_profit,
    }


BUSINESS_METHODS = {
    "pareto_abc": pareto_abc,
    "contribution": contribution_analysis,
    "funnel": funnel_analysis,
    "cohort": cohort_analysis,
    "rfm": rfm_segmentation,
    "break_even": break_even_analysis,
}


def business_engine(action: str, params_json: str = "{}") -> dict:
    """General business-analysis engine.

    Actions: pareto_abc, contribution, funnel, cohort, rfm, break_even.
    `params_json` is a JSON object with keyword arguments for the selected action.
    """
    if action not in BUSINESS_METHODS:
        raise ValueError(
            f"Unknown action '{action}'. Available: {', '.join(sorted(BUSINESS_METHODS))}"
        )
    params = json.loads(params_json or "{}")
    if not isinstance(params, dict):
        raise ValueError("params_json JSON object olmalı")
    return {"action": action, "result": BUSINESS_METHODS[action](**params)}
