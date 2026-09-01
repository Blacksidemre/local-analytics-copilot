from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def build_credit_risk_regression_fixture(seed: int = 20260829) -> pd.DataFrame:
    """Build the controlled 1,508 x 22 ingestion regression dataset."""
    rng = np.random.default_rng(seed)
    rows = 1500
    regions = np.array(["Marmara", "Ege", "İç Anadolu", "Akdeniz", "Karadeniz"])
    segments = np.array(["Mass", "Affluent", "SME", "Emerging"])
    products = np.array(["Kredi Kartı", "İhtiyaç Kredisi", "KMH", "Taşıt Kredisi"])
    legal_statuses = np.array(["Takipsiz", "İhtar", "Yasal Takip"])

    income = np.maximum(rng.lognormal(mean=10.2, sigma=0.45, size=rows), 8_000).round(2)
    credit_limit = np.maximum(income * rng.uniform(0.7, 3.4, rows), 5_000).round(2)
    utilization = np.clip(rng.beta(2.2, 2.0, rows), 0.01, 1.25)
    outstanding = (credit_limit * utilization).round(2)
    payment_ratio = np.clip(1.05 - utilization * 0.55 + rng.normal(0, 0.12, rows), 0, 1.3)
    dpd = np.maximum(0, rng.negative_binomial(2, 0.09, rows) - 4)
    bureau = np.clip(790 - utilization * 230 - dpd * 1.2 + rng.normal(0, 35, rows), 250, 900)
    restructure = ((dpd >= 60) & (rng.random(rows) < 0.38)).astype(int)
    score = (
        -4.0
        + utilization * 2.2
        + np.minimum(dpd, 180) / 60 * 0.75
        - payment_ratio * 1.4
        - (bureau - 500) / 180
        + restructure * 0.7
    )
    probability = 1 / (1 + np.exp(-score))

    frame = pd.DataFrame(
        {
            "customer_id": [f"CUST-{index + 1:06d}" for index in range(rows)],
            "snapshot_date": pd.Timestamp("2026-01-31"),
            "region": rng.choice(regions, rows, p=[0.35, 0.18, 0.2, 0.16, 0.11]),
            "customer_segment": rng.choice(segments, rows, p=[0.55, 0.13, 0.17, 0.15]),
            "product_type": rng.choice(products, rows, p=[0.42, 0.35, 0.15, 0.08]),
            "age": rng.integers(21, 76, rows),
            "monthly_income_try": income,
            "employment_years": np.round(rng.uniform(0, 35, rows), 1),
            "outstanding_balance_try": outstanding,
            "credit_limit_try": credit_limit,
            "utilization_rate": np.round(utilization, 4),
            "dpd": dpd,
            "payment_ratio_3m": np.round(payment_ratio, 4),
            "promises_kept_6m": rng.binomial(6, np.clip(payment_ratio / 1.3, 0.05, 0.95)),
            "contacts_3m": rng.poisson(3.5, rows),
            "account_tenure_months": rng.integers(3, 181, rows),
            "legal_status": np.where(
                dpd >= 90,
                rng.choice(legal_statuses[1:], rows),
                legal_statuses[0],
            ),
            "restructure_flag": restructure,
            "recent_collection_try": np.round(
                outstanding * payment_ratio * rng.uniform(0, 0.18, rows), 2
            ),
            "bureau_score": np.round(bureau).astype(int),
            "macro_unemployment_pct": np.round(rng.normal(9.2, 0.35, rows), 2),
            "default_next_30d": rng.binomial(1, probability),
        }
    )

    frame.loc[100:123, "monthly_income_try"] = np.nan
    frame.loc[200:211, "payment_ratio_3m"] = np.nan
    frame.loc[300:315, "employment_years"] = np.nan
    return pd.concat([frame, frame.iloc[:8].copy()], ignore_index=True)


def write_credit_risk_regression_fixture(output_directory: Path) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    frame = build_credit_risk_regression_fixture()
    csv_path = output_directory / "Kredi_Temerrut_Riski_Sentetik_Test.csv"
    xlsx_path = output_directory / "Kredi_Temerrut_Riski_Sentetik_Test.xlsx"
    frame.to_csv(csv_path, index=False)
    frame.to_excel(xlsx_path, index=False, engine="openpyxl")
    return {"csv": csv_path, "xlsx": xlsx_path}
