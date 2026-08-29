from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
n = 5000
start = pd.Timestamp("2024-01-01")
purchase = start + pd.to_timedelta(rng.integers(0, 540, n), unit="D")
dpd = np.clip(rng.gamma(shape=2.0, scale=170, size=n).astype(int), 0, 1400)
balance = np.exp(rng.normal(10.1, 1.0, n)).round(2)
recovery = np.clip(0.22 * np.exp(-dpd / 1100) + rng.normal(0, 0.035, n), 0, 0.5)
collection = (balance * recovery).round(2)
portfolio = rng.choice(["P_A", "P_B", "P_C", "P_D"], n, p=[0.3, 0.27, 0.23, 0.2])
legal = rng.choice(["Pre-Legal", "Legal", "Execution", "Settlement"], n, p=[0.35, 0.30, 0.25, 0.10])

df = pd.DataFrame(
    {
        "account_id": [f"A{i:07d}" for i in range(1, n + 1)],
        "debtor_id": [f"D{int(i / 1.4):07d}" for i in range(1, n + 1)],
        "portfolio": portfolio,
        "purchase_date": purchase,
        "dpd": dpd,
        "legal_status": legal,
        "total_balance": balance,
        "cumulative_collection": collection,
        "target_collection": (balance * np.clip(recovery * 1.08, 0, 0.55)).round(2),
    }
)
df["recovery_rate_demo"] = np.where(
    df.total_balance > 0, df.cumulative_collection / df.total_balance, 0
)
out = Path("workspace/incoming/demo_npl.csv")
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False)

# Separate collection-events sample for vintage analysis.
ev = []
for _, r in df.head(1200).iterrows():
    k = int(rng.integers(1, 7))
    months = np.sort(rng.integers(0, 30, k))
    total = float(r.cumulative_collection)
    if total <= 0:
        continue
    weights = rng.dirichlet(np.ones(k))
    for m, w in zip(months, weights, strict=True):
        ev.append(
            {
                "account_id": r.account_id,
                "portfolio": r.portfolio,
                "purchase_date": r.purchase_date,
                "collection_date": r.purchase_date + pd.DateOffset(months=int(m)),
                "collection_amount": round(total * float(w), 2),
            }
        )
pd.DataFrame(ev).to_csv("workspace/incoming/demo_collections.csv", index=False)
print(out)
