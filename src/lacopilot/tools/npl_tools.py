from __future__ import annotations

import math

import numpy as np
import pandas as pd

from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table


def npl_portfolio_summary(
    file_path: str,
    balance_column: str,
    collection_column: str,
    dpd_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Calculate basic NPL portfolio KPIs and optional DPD aging.

    Args:
        file_path: Workspace-relative dataset path.
        balance_column: Outstanding/face balance column.
        collection_column: Collection amount column.
        dpd_column: Optional days-past-due column.
        sheet_name: Excel sheet or numeric index as text.
    """
    s = get_settings()
    path = resolve_workspace_path(s.workspace, file_path)
    sheet = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    df = load_table(path, sheet)
    for c in [balance_column, collection_column]:
        if c not in df:
            raise KeyError(f"Kolon bulunamadı: {c}")
    balance = pd.to_numeric(df[balance_column], errors="coerce")
    coll = pd.to_numeric(df[collection_column], errors="coerce")
    total_balance = float(balance.sum(skipna=True))
    total_collection = float(coll.sum(skipna=True))
    result = {
        "rows": int(len(df)),
        "total_balance": total_balance,
        "total_collection": total_collection,
        "simple_collection_to_balance_ratio": None
        if total_balance == 0
        else total_collection / total_balance,
        "warning": "Bu oran şirketinizin resmi Recovery Rate tanımı olmayabilir. Onaylı iş kuralı ayrıca tanımlanmalıdır.",
    }
    if dpd_column:
        if dpd_column not in df:
            raise KeyError(f"Kolon bulunamadı: {dpd_column}")
        dpd = pd.to_numeric(df[dpd_column], errors="coerce")
        bins = [-np.inf, 0, 30, 60, 90, 180, 360, 720, np.inf]
        labels = ["<=0", "1-30", "31-60", "61-90", "91-180", "181-360", "361-720", "720+"]
        bucket = pd.cut(dpd, bins=bins, labels=labels)
        temp = pd.DataFrame({"bucket": bucket, "balance": balance, "collection": coll})
        aging = (
            temp.groupby("bucket", observed=False)
            .agg(
                accounts=("bucket", "size"),
                balance=("balance", "sum"),
                collection=("collection", "sum"),
            )
            .reset_index()
        )
        result["dpd_aging"] = aging.assign(bucket=aging["bucket"].astype(str)).to_dict(
            orient="records"
        )
    return result


def valuation_scenario(
    face_value: float,
    expected_recovery_rate: float,
    months_to_recovery: float,
    annual_discount_rate: float,
    purchase_price: float | None = None,
) -> dict:
    """Calculate a simple discounted expected recovery, NPV-style value and optional MOIC.

    Args:
        face_value: Portfolio/account face value.
        expected_recovery_rate: Expected recovery as decimal, e.g. 0.12.
        months_to_recovery: Expected collection timing in months.
        annual_discount_rate: Annual discount rate as decimal.
        purchase_price: Optional purchase price for MOIC calculation.
    """
    values = [face_value, expected_recovery_rate, months_to_recovery, annual_discount_rate]
    if purchase_price is not None:
        values.append(purchase_price)
    if not all(math.isfinite(float(value)) for value in values) or (
        face_value < 0
        or not 0 <= expected_recovery_rate <= 1
        or months_to_recovery < 0
        or annual_discount_rate <= -1
        or (purchase_price is not None and purchase_price <= 0)
    ):
        raise ValueError("Girdiler geçersiz")
    expected = face_value * expected_recovery_rate
    monthly = (1 + annual_discount_rate) ** (1 / 12) - 1
    pv = expected / ((1 + monthly) ** months_to_recovery)
    return {
        "expected_recovery": expected,
        "present_value": pv,
        "gross_moic": None if not purchase_price else expected / purchase_price,
        "note": "Bu tek-nakit-akışı basit senaryodur; production değerleme çok dönemli cash-flow curve kullanmalıdır.",
    }
