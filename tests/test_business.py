from pathlib import Path

import pandas as pd

from lacopilot.config import get_settings
from lacopilot.tools.business_tools import break_even_analysis, business_engine


def setup(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path))
    get_settings.cache_clear()
    s = get_settings()
    s.ensure_dirs()
    df = pd.DataFrame(
        {
            "customer": ["A", "A", "B", "C", "C", "C"],
            "date": pd.to_datetime(
                ["2026-01-01", "2026-02-01", "2026-01-15", "2026-01-02", "2026-02-02", "2026-03-02"]
            ),
            "amount": [100, 120, 80, 60, 70, 90],
            "stage1": [1, 1, 1, 1, 1, 1],
            "stage2": [1, 1, 0, 1, 0, 1],
            "stage3": [1, 0, 0, 1, 0, 0],
        }
    )
    df.to_csv(s.incoming_dir / "biz.csv", index=False)
    return s


def test_business_engine(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    r = business_engine(
        "pareto_abc",
        '{"file_path":"incoming/biz.csv","entity_column":"customer","value_column":"amount"}',
    )
    assert r["result"]["entities"] == 3
    f = business_engine(
        "funnel", '{"file_path":"incoming/biz.csv","stages":["stage1","stage2","stage3"]}'
    )
    assert len(f["result"]["stages"]) == 3
    b = break_even_analysis(1000, 50, 30)
    assert b["required_units"] == 50
