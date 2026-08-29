from pathlib import Path

import pandas as pd

from lacopilot.config import get_settings
from lacopilot.tools.advanced_tools import (
    bootstrap_mean_ci,
    dataset_drift,
    monte_carlo_npv,
    paired_comparison,
)
from lacopilot.tools.bi_tools import create_excel_dashboard, pivot_analysis
from lacopilot.tools.npl_advanced import (
    actual_vs_target,
    concentration_analysis,
    dpd_aging,
    portfolio_valuation_scenarios,
)
from lacopilot.tools.router_tools import analytics_engine


def setup(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path))
    get_settings.cache_clear()
    s = get_settings()
    s.ensure_dirs()
    df = pd.DataFrame(
        {
            "account_id": range(1, 31),
            "debtor": [f"D{i // 2}" for i in range(30)],
            "portfolio": ["A"] * 15 + ["B"] * 15,
            "before": range(10, 40),
            "after": range(12, 42),
            "balance": [1000 + i * 100 for i in range(30)],
            "collection": [50 + i * 5 for i in range(30)],
            "dpd": [0, 10, 35, 65, 95, 190, 365, 800, 20, 50] * 3,
            "target": [100] * 30,
            "actual": [95 + i % 10 for i in range(30)],
        }
    )
    df.to_csv(s.incoming_dir / "npl.csv", index=False)
    df2 = df.copy()
    df2["balance"] = df2["balance"] * 1.2
    df2.to_csv(s.incoming_dir / "npl2.csv", index=False)
    return s


def test_advanced_stats(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    p = paired_comparison("incoming/npl.csv", "before", "after")
    assert p["n"] == 30 and p["mean_difference_after_minus_before"] == 2
    b = bootstrap_mean_ci("incoming/npl.csv", "balance", iterations=600)
    assert b["bootstrap_ci"][0] < b["mean"] < b["bootstrap_ci"][1]
    d = dataset_drift("incoming/npl.csv", "incoming/npl2.csv", columns=["balance"])
    assert d["columns"][0]["type"] == "numeric"
    m = monte_carlo_npv(1_000_000, 100_000, 0.2, 0.03, 24, 3, 0.25, simulations=2000)
    assert m["npv"]["mean"] > 0


def test_bi_and_npl(tmp_path, monkeypatch):
    s = setup(tmp_path, monkeypatch)
    p = pivot_analysis("incoming/npl.csv", ["portfolio"], ["balance"], output_name="p.xlsx")
    assert (s.workspace / p["output"]).exists()
    d = create_excel_dashboard(
        "incoming/npl.csv",
        output_name="d.xlsx",
        category_column="portfolio",
        value_column="balance",
    )
    assert (s.workspace / d["output"]).exists()
    aging = dpd_aging("incoming/npl.csv", "dpd", "balance", "collection", "account_id")
    assert len(aging["buckets"]) == 8
    c = concentration_analysis("incoming/npl.csv", "debtor", "balance")
    assert c["debtors"] > 0
    a = actual_vs_target("incoming/npl.csv", "actual", "target", ["portfolio"])
    assert len(a["rows"]) == 2
    v = portfolio_valuation_scenarios(1_000_000, 100_000, 0.2, 24, 0.25)
    assert len(v["scenarios"]) == 9


def test_router(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    r = analytics_engine("descriptive", '{"file_path":"incoming/npl.csv","columns":["balance"]}')
    assert "balance" in r["result"]["columns"]
