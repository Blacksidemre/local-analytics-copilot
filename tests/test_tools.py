from pathlib import Path

import pandas as pd

from lacopilot.config import get_settings
from lacopilot.tools.data_tools import inspect_dataset, profile_dataset
from lacopilot.tools.npl_tools import valuation_scenario
from lacopilot.tools.statistics_tools import compare_two_groups


def setup_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path))
    get_settings.cache_clear()
    s = get_settings()
    s.ensure_dirs()
    df = pd.DataFrame(
        {
            "group": ["A"] * 10 + ["B"] * 10,
            "value": [1, 2, 3, 4, 5, 3, 4, 5, 2, 4, 8, 9, 10, 8, 9, 11, 7, 10, 9, 8],
        }
    )
    path = s.incoming_dir / "demo.csv"
    df.to_csv(path, index=False)
    return s


def test_profile(tmp_path, monkeypatch):
    setup_workspace(tmp_path, monkeypatch)
    x = inspect_dataset("incoming/demo.csv")
    assert x["rows"] == 20
    p = profile_dataset("incoming/demo.csv")
    assert p["columns"] == 2


def test_stats(tmp_path, monkeypatch):
    setup_workspace(tmp_path, monkeypatch)
    r = compare_two_groups("incoming/demo.csv", "value", "group", "A", "B")
    assert r["p_value"] < 0.05


def test_valuation():
    r = valuation_scenario(100000, 0.12, 24, 0.30, 3000)
    assert r["expected_recovery"] == 12000
    assert r["present_value"] > 0
