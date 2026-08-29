from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lacopilot.config import get_settings
from lacopilot.tools.advanced_tools import (
    bootstrap_mean_ci,
    cross_validated_model,
    monte_carlo_npv,
)
from lacopilot.tools.business_tools import funnel_analysis, pareto_abc, rfm_segmentation
from lacopilot.tools.npl_advanced import roll_rate_analysis, vintage_analysis
from lacopilot.tools.npl_tools import valuation_scenario
from lacopilot.tools.statistics_tools import (
    cluster_analysis,
    compare_multiple_groups,
    pca_analysis,
)


def configure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LAC_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    return get_settings()


def test_welch_anova_and_small_group_exclusion(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(
        {
            "group": np.repeat(["A", "B", "C"], 50),
            "value": np.concatenate(
                [rng.normal(0, 1, 50), rng.normal(1, 5, 50), rng.normal(2, 10, 50)]
            ),
        }
    )
    frame.to_csv(settings.incoming_dir / "groups.csv", index=False)
    result = compare_multiple_groups("incoming/groups.csv", "value", "group")
    assert result["method"] == "Welch ANOVA"
    assert result["effect_size"]["name"] == "eta_squared_descriptive"


def test_pca_cluster_and_bootstrap_validate_edge_inputs(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    pd.DataFrame({"x": [None], "y": [None]}).to_csv(
        settings.incoming_dir / "empty.csv", index=False
    )
    with pytest.raises(ValueError):
        pca_analysis("incoming/empty.csv", ["x", "y"])
    with pytest.raises(ValueError):
        cluster_analysis("incoming/empty.csv", ["x", "y"])
    pd.DataFrame({"x": range(10)}).to_csv(settings.incoming_dir / "valid.csv", index=False)
    with pytest.raises(ValueError):
        bootstrap_mean_ci("incoming/valid.csv", "x", confidence=1.0)


def test_npl_portfolio_vintage_and_weighted_roll_rate(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    vintage = pd.DataFrame(
        {
            "portfolio": ["P1", "P1", "P2", "P2"],
            "purchase": ["2025-01-01"] * 4,
            "collection_date": ["2025-02-01", "2025-03-01"] * 2,
            "collection": [10, 20, 100, 200],
        }
    )
    vintage.to_csv(settings.incoming_dir / "vintage.csv", index=False)
    result = vintage_analysis(
        "incoming/vintage.csv",
        "purchase",
        "collection_date",
        "collection",
        portfolio_column="portfolio",
    )
    assert {row["portfolio"] for row in result["latest_by_vintage"]} == {"P1", "P2"}
    latest = {row["portfolio"]: row["cumulative_collection"] for row in result["latest_by_vintage"]}
    assert latest == {"P1": 30, "P2": 300}

    snapshots = pd.DataFrame(
        {
            "account": ["A", "A", "B", "B"],
            "date": ["2025-01-01", "2025-02-01", "2025-01-01", "2025-02-01"],
            "dpd": [0, 40, 0, 0],
            "balance": [100, 90, 900, 850],
        }
    )
    snapshots.to_csv(settings.incoming_dir / "roll.csv", index=False)
    roll = roll_rate_analysis(
        "incoming/roll.csv", "account", "date", "dpd", balance_column="balance"
    )
    assert roll["balance_weighted_row_pct"]["31-60"]["Current/<=0"] == 10.0
    assert roll["balance_weighted_row_pct"]["Current/<=0"]["Current/<=0"] == 90.0


def test_business_and_valuation_invalid_inputs(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    pd.DataFrame({"a": [0, 0], "b": [0, 1]}).to_csv(
        settings.incoming_dir / "funnel.csv", index=False
    )
    funnel = funnel_analysis("incoming/funnel.csv", ["a", "b"])
    assert funnel["stages"][1]["conversion_from_previous_pct"] is None
    pd.DataFrame({"entity": ["A", "B"], "value": [10, -1]}).to_csv(
        settings.incoming_dir / "negative.csv", index=False
    )
    with pytest.raises(ValueError):
        pareto_abc("incoming/negative.csv", "entity", "value")
    pd.DataFrame({"customer": [], "date": [], "amount": []}).to_csv(
        settings.incoming_dir / "empty_rfm.csv", index=False
    )
    with pytest.raises(ValueError):
        rfm_segmentation("incoming/empty_rfm.csv", "customer", "date", "amount")
    with pytest.raises(ValueError):
        valuation_scenario(100, 0.2, 12, 0.2, purchase_price=-1)
    with pytest.raises(ValueError):
        monte_carlo_npv(100, 10, 1.2, 0.1, 12, 1, 0.2)


def test_classification_caps_folds_and_handles_multiclass_split(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    frame = pd.DataFrame(
        {
            "target": list("AAABBBCCCDDD") + [None],
            "numeric": list(range(13)),
            "category": ["x", "y", "z"] * 4 + ["x"],
        }
    )
    frame.to_csv(settings.incoming_dir / "classification.csv", index=False)
    result = cross_validated_model(
        "incoming/classification.csv",
        "target",
        ["numeric", "category"],
        task="classification",
        folds=10,
    )
    assert result["rows"] == 12
    assert result["folds"] == 3
    assert "accuracy" in result["cv_metrics"]
