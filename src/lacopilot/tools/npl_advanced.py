from __future__ import annotations

import numpy as np
import pandas as pd

from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table


def _load(file_path: str, sheet_name: str = "0") -> pd.DataFrame:
    s = get_settings()
    p = resolve_workspace_path(s.workspace, file_path)
    sheet = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    return load_table(p, sheet)


def dpd_aging(
    file_path: str,
    dpd_column: str,
    balance_column: str,
    collection_column: str | None = None,
    account_id_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Create standard NPL DPD aging buckets and summary metrics."""
    df = _load(file_path, sheet_name)
    required = [dpd_column, balance_column] + ([collection_column] if collection_column else [])
    missing = [c for c in required if c not in df]
    if missing:
        raise KeyError(f"Kolonlar bulunamadı: {missing}")
    dpd = pd.to_numeric(df[dpd_column], errors="coerce")
    bal = pd.to_numeric(df[balance_column], errors="coerce").fillna(0)
    bins = [-np.inf, 0, 30, 60, 90, 180, 360, 720, np.inf]
    labels = ["Current/<=0", "1-30", "31-60", "61-90", "91-180", "181-360", "361-720", "720+"]
    work = pd.DataFrame({"bucket": pd.cut(dpd, bins=bins, labels=labels), "balance": bal})
    if collection_column:
        work["collection"] = pd.to_numeric(df[collection_column], errors="coerce").fillna(0)
    if account_id_column and account_id_column in df:
        work["account_id"] = df[account_id_column]
    agg = {"balance": "sum"}
    if collection_column:
        agg["collection"] = "sum"
    if "account_id" in work:
        agg["account_id"] = pd.Series.nunique
    result = work.groupby("bucket", observed=False).agg(agg).reset_index()
    if "account_id" in result:
        result = result.rename(columns={"account_id": "accounts"})
    else:
        result["accounts"] = work.groupby("bucket", observed=False).size().to_numpy()
    total_bal = float(result["balance"].sum())
    result["balance_share_pct"] = np.where(total_bal, result["balance"] / total_bal * 100, 0)
    if collection_column:
        result["recovery_on_balance_pct"] = np.where(
            result["balance"] != 0, result["collection"] / result["balance"] * 100, np.nan
        )
    return {
        "buckets": result.replace({np.nan: None}).to_dict(orient="records"),
        "total_balance": total_bal,
        "definition_note": "DPD bucket definitions are configurable business rules; validate against company policy.",
    }


def concentration_analysis(
    file_path: str, debtor_column: str, balance_column: str, sheet_name: str = "0"
) -> dict:
    """Compute debtor concentration, top-N shares and HHI."""
    df = _load(file_path, sheet_name)
    work = df[[debtor_column, balance_column]].copy()
    work[balance_column] = pd.to_numeric(work[balance_column], errors="coerce").fillna(0)
    g = work.groupby(debtor_column, dropna=False)[balance_column].sum().sort_values(ascending=False)
    total = float(g.sum())
    shares = g / total if total else g * 0
    hhi = float((shares**2).sum()) if len(shares) else 0.0

    def share(n: int):
        return float(shares.head(n).sum() * 100)

    return {
        "debtors": int(len(g)),
        "total_balance": total,
        "top1_pct": share(1),
        "top5_pct": share(5),
        "top10_pct": share(10),
        "top50_pct": share(50),
        "hhi": hhi,
        "top_debtors": [
            {"debtor": str(i), "balance": float(v), "share_pct": float(shares.loc[i] * 100)}
            for i, v in g.head(20).items()
        ],
    }


def vintage_analysis(
    file_path: str,
    purchase_date_column: str,
    collection_date_column: str,
    collection_amount_column: str,
    portfolio_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Build cumulative collection curves by purchase-quarter vintage and months-on-book (MOB)."""
    df = _load(file_path, sheet_name)
    cols = [purchase_date_column, collection_date_column, collection_amount_column] + (
        [portfolio_column] if portfolio_column else []
    )
    work = df[cols].copy()
    work[purchase_date_column] = pd.to_datetime(work[purchase_date_column], errors="coerce")
    work[collection_date_column] = pd.to_datetime(work[collection_date_column], errors="coerce")
    work[collection_amount_column] = pd.to_numeric(work[collection_amount_column], errors="coerce")
    work = work.dropna(
        subset=[purchase_date_column, collection_date_column, collection_amount_column]
    )
    work["vintage"] = work[purchase_date_column].dt.to_period("Q").astype(str)
    work["mob"] = (
        work[collection_date_column].dt.year - work[purchase_date_column].dt.year
    ) * 12 + (work[collection_date_column].dt.month - work[purchase_date_column].dt.month)
    work = work[work["mob"] >= 0]
    segment_cols = [portfolio_column] if portfolio_column else []
    group_cols = segment_cols + ["vintage", "mob"]
    agg = (
        work.groupby(group_cols)[collection_amount_column]
        .sum()
        .reset_index()
        .sort_values(group_cols)
    )
    curve_group = segment_cols + ["vintage"]
    agg["cumulative_collection"] = agg.groupby(curve_group)[collection_amount_column].cumsum()
    records = agg.head(5000).to_dict(orient="records")
    latest = agg.sort_values("mob").groupby(curve_group).tail(1)
    return {
        "rows_used": int(len(work)),
        "curve": records,
        "latest_by_vintage": latest.to_dict(orient="records"),
        "note": "Vintage curves compare timing patterns; normalize by face value/purchase price when comparing differently sized portfolios.",
    }


def roll_rate_analysis(
    file_path: str,
    account_id_column: str,
    snapshot_date_column: str,
    dpd_column: str,
    balance_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Create DPD migration/roll-rate matrix from repeated account snapshots."""
    df = _load(file_path, sheet_name)
    cols = [account_id_column, snapshot_date_column, dpd_column] + (
        [balance_column] if balance_column else []
    )
    work = df[cols].copy()
    work[snapshot_date_column] = pd.to_datetime(work[snapshot_date_column], errors="coerce")
    work[dpd_column] = pd.to_numeric(work[dpd_column], errors="coerce")
    if balance_column:
        work[balance_column] = pd.to_numeric(work[balance_column], errors="coerce").fillna(0)
    work = work.dropna(subset=[account_id_column, snapshot_date_column, dpd_column]).sort_values(
        [account_id_column, snapshot_date_column]
    )
    bins = [-np.inf, 0, 30, 60, 90, 180, 360, 720, np.inf]
    labels = ["Current/<=0", "1-30", "31-60", "61-90", "91-180", "181-360", "361-720", "720+"]
    work["from_bucket"] = pd.cut(work[dpd_column], bins=bins, labels=labels).astype(str)
    work["to_bucket"] = work.groupby(account_id_column)["from_bucket"].shift(-1)
    transitions = work.dropna(subset=["to_bucket"])
    counts = pd.crosstab(transitions["from_bucket"], transitions["to_bucket"])
    rates = (
        pd.crosstab(transitions["from_bucket"], transitions["to_bucket"], normalize="index") * 100
    )
    result = {
        "transition_count": int(len(transitions)),
        "counts": counts.to_dict(),
        "row_pct": rates.round(3).to_dict(),
        "note": "The matrix reflects observed snapshot-to-snapshot migration; consistent snapshot spacing is important.",
    }
    if balance_column:
        weighted = transitions.pivot_table(
            index="from_bucket",
            columns="to_bucket",
            values=balance_column,
            aggfunc="sum",
            fill_value=0,
        )
        denominator = weighted.sum(axis=1).replace(0, np.nan)
        weighted_rates = weighted.div(denominator, axis=0) * 100
        result["balance_amounts"] = weighted.to_dict()
        result["balance_weighted_row_pct"] = (
            weighted_rates.round(3).replace({np.nan: None}).to_dict()
        )
    return result


def actual_vs_target(
    file_path: str,
    actual_column: str,
    target_column: str,
    group_columns: list[str] | None = None,
    sheet_name: str = "0",
) -> dict:
    df = _load(file_path, sheet_name)
    groups = group_columns or []
    work = df[groups + [actual_column, target_column]].copy()
    work[actual_column] = pd.to_numeric(work[actual_column], errors="coerce").fillna(0)
    work[target_column] = pd.to_numeric(work[target_column], errors="coerce").fillna(0)
    if groups:
        agg = work.groupby(groups, dropna=False)[[actual_column, target_column]].sum().reset_index()
    else:
        agg = pd.DataFrame(
            [{actual_column: work[actual_column].sum(), target_column: work[target_column].sum()}]
        )
    agg["variance"] = agg[actual_column] - agg[target_column]
    agg["achievement_pct"] = np.where(
        agg[target_column] != 0, agg[actual_column] / agg[target_column] * 100, np.nan
    )
    return {"rows": agg.replace({np.nan: None}).to_dict(orient="records")}


def portfolio_valuation_scenarios(
    face_value: float,
    purchase_price: float,
    base_recovery_rate: float,
    months_to_recovery: float,
    annual_discount_rate: float,
    recovery_multipliers: list[float] | None = None,
    discount_rate_shocks: list[float] | None = None,
) -> dict:
    """Scenario grid for NPV, MOIC and margin. Rates are decimals, e.g. 0.20 = 20%."""
    values = [
        face_value,
        purchase_price,
        base_recovery_rate,
        months_to_recovery,
        annual_discount_rate,
    ]
    if (
        not all(np.isfinite(float(value)) for value in values)
        or face_value < 0
        or purchase_price <= 0
        or not 0 <= base_recovery_rate <= 1
        or months_to_recovery < 0
        or annual_discount_rate <= -1
    ):
        raise ValueError("Değerleme senaryosu girdileri geçersiz")
    multipliers = recovery_multipliers or [0.75, 1.0, 1.25]
    shocks = discount_rate_shocks or [0.10, 0.0, -0.05]
    if len(multipliers) > 20 or len(shocks) > 20:
        raise ValueError("Scenario grid eksen başına en fazla 20 değer içerebilir")
    rows = []
    for rm in multipliers:
        for shock in shocks:
            rr = max(0.0, min(1.0, base_recovery_rate * rm))
            dr = max(-0.95, annual_discount_rate + shock)
            expected = face_value * rr
            monthly = (1 + dr) ** (1 / 12) - 1
            npv = expected / ((1 + monthly) ** months_to_recovery)
            moic = expected / purchase_price if purchase_price else None
            rows.append(
                {
                    "recovery_multiplier": rm,
                    "recovery_rate": rr,
                    "discount_rate": dr,
                    "expected_collection": expected,
                    "npv": npv,
                    "purchase_price": purchase_price,
                    "npv_margin": npv - purchase_price,
                    "moic": moic,
                }
            )
    return {
        "scenarios": rows,
        "guardrail": "Scenario outputs depend on recovery timing/definition assumptions and are not a bid recommendation without approved policy.",
    }
