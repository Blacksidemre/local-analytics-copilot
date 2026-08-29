from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table, serializable


def _load(file_path: str, sheet_name: str = "0") -> pd.DataFrame:
    s = get_settings()
    p = resolve_workspace_path(s.workspace, file_path)
    sh = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    return load_table(p, sh)


def paired_comparison(
    file_path: str, before_column: str, after_column: str, sheet_name: str = "0"
) -> dict:
    """Paired t-test or Wilcoxon signed-rank after normality check of paired differences."""
    df = _load(file_path, sheet_name)
    work = df[[before_column, after_column]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(work) < 5:
        raise ValueError("Paired comparison için en az 5 complete pair gerekli")
    diff = (work[after_column] - work[before_column]).to_numpy(dtype=float)
    sample = (
        diff if len(diff) <= 5000 else np.random.default_rng(42).choice(diff, 5000, replace=False)
    )
    diff_sd = float(np.std(diff, ddof=1))
    pnorm = 1.0 if diff_sd == 0 else float(stats.shapiro(sample).pvalue)
    if pnorm >= 0.05:
        method = "Paired t-test"
        if diff_sd == 0:
            mean_diff = float(np.mean(diff))
            statistic = float("inf") if mean_diff != 0 else 0.0
            pvalue = 0.0 if mean_diff != 0 else 1.0
            dz = None
        else:
            test = stats.ttest_rel(work[after_column], work[before_column])
            statistic = float(test.statistic)
            pvalue = float(test.pvalue)
            dz = float(np.mean(diff) / diff_sd)
        effect = {"name": "Cohen's dz", "value": dz}
    else:
        test = stats.wilcoxon(diff, alternative="two-sided", zero_method="wilcox")
        method = "Wilcoxon signed-rank"
        effect = {"name": "median paired difference", "value": float(np.median(diff))}
    return {
        "method": method,
        "n": len(work),
        "before_mean": float(work[before_column].mean()),
        "after_mean": float(work[after_column].mean()),
        "mean_difference_after_minus_before": float(np.mean(diff)),
        "median_difference": float(np.median(diff)),
        "difference_normality_p": pnorm,
        "statistic": statistic if method == "Paired t-test" else float(test.statistic),
        "p_value": pvalue if method == "Paired t-test" else float(test.pvalue),
        "effect_size": effect,
        "guardrail": "Pairing must reflect the same unit measured twice or a valid matched design.",
    }


def bootstrap_mean_ci(
    file_path: str,
    column: str,
    confidence: float = 0.95,
    iterations: int = 5000,
    sheet_name: str = "0",
) -> dict:
    """Nonparametric bootstrap confidence interval for a mean."""
    x = (
        pd.to_numeric(_load(file_path, sheet_name)[column], errors="coerce")
        .dropna()
        .to_numpy(dtype=float)
    )
    if len(x) < 5:
        raise ValueError("En az 5 geçerli gözlem gerekli")
    if not 0.5 <= float(confidence) < 1:
        raise ValueError("confidence 0.5 dahil, 1 hariç aralığında olmalı")
    iterations = max(500, min(int(iterations), 20000))
    rng = np.random.default_rng(42)
    means = np.empty(iterations, dtype=float)
    for i in range(iterations):
        means[i] = rng.choice(x, size=len(x), replace=True).mean()
    alpha = (1 - confidence) / 2
    lo, hi = np.quantile(means, [alpha, 1 - alpha])
    return {
        "n": len(x),
        "mean": float(np.mean(x)),
        "confidence": confidence,
        "iterations": iterations,
        "bootstrap_ci": [float(lo), float(hi)],
    }


def dataset_drift(
    file_a: str,
    file_b: str,
    columns: list[str] | None = None,
    sheet_a: str = "0",
    sheet_b: str = "0",
) -> dict:
    """Screen numeric/categorical distribution drift between two datasets."""
    a = _load(file_a, sheet_a)
    b = _load(file_b, sheet_b)
    common = [c for c in a.columns if c in b.columns]
    use = columns or common
    rows = []
    for c in use:
        if c not in a or c not in b:
            continue
        an = pd.to_numeric(a[c], errors="coerce").dropna()
        bn = pd.to_numeric(b[c], errors="coerce").dropna()
        numeric = len(an) >= max(5, int(0.5 * a[c].notna().sum())) and len(bn) >= max(
            5, int(0.5 * b[c].notna().sum())
        )
        if numeric:
            ks = stats.ks_2samp(an, bn)
            rows.append(
                {
                    "column": c,
                    "type": "numeric",
                    "ks_stat": float(ks.statistic),
                    "p_value": float(ks.pvalue),
                    "mean_a": serializable(an.mean()),
                    "mean_b": serializable(bn.mean()),
                }
            )
        else:
            av = a[c].astype("string").value_counts(normalize=True)
            bv = b[c].astype("string").value_counts(normalize=True)
            cats = av.index.union(bv.index)
            pa = av.reindex(cats, fill_value=0).to_numpy()
            pb = bv.reindex(cats, fill_value=0).to_numpy()
            tv = float(0.5 * np.abs(pa - pb).sum())
            rows.append(
                {
                    "column": c,
                    "type": "categorical",
                    "total_variation_distance": tv,
                    "unique_a": int(a[c].nunique()),
                    "unique_b": int(b[c].nunique()),
                }
            )
    return {
        "columns": rows,
        "guardrail": "Drift flags a distribution change; it does not identify root cause by itself.",
    }


def cross_validated_model(
    file_path: str,
    target: str,
    predictors: list[str],
    task: str = "auto",
    folds: int = 5,
    sheet_name: str = "0",
) -> dict:
    """Baseline random-forest model with cross-validation and permutation importance.

    Intended for screening, not automatic production deployment. Numeric/categorical predictors are preprocessed.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import KFold, StratifiedKFold, cross_validate, train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    task = task.lower()
    if not predictors or len(set(predictors)) != len(predictors):
        raise ValueError("predictors boş olamaz ve tekrar eden kolon içeremez")
    if target in predictors:
        raise ValueError("target predictors içinde olamaz")
    df = _load(file_path, sheet_name)
    work = df[[target] + predictors].copy()
    y = work.pop(target)
    if task == "auto":
        task = (
            "classification"
            if y.nunique(dropna=True) <= 20 or str(y.dtype) in {"object", "category", "bool"}
            else "regression"
        )
    numeric = [c for c in predictors if pd.api.types.is_numeric_dtype(work[c])]
    categorical = [c for c in predictors if c not in numeric]
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), numeric),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
        ]
    )
    folds = max(3, min(int(folds), 10))
    if task == "classification":
        valid = y.notna()
        work = work.loc[valid]
        y = y.loc[valid]
        counts = y.value_counts()
        if len(counts) < 2:
            raise ValueError("Classification target en az iki sınıf içermeli")
        folds = min(folds, int(counts.min()))
        if folds < 2:
            raise ValueError("Her sınıfta cross-validation için en az 2 gözlem gerekli")
        model = RandomForestClassifier(
            n_estimators=250, random_state=42, class_weight="balanced", n_jobs=-1
        )
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
        scoring = {"accuracy": "accuracy", "f1_macro": "f1_macro"}
        if y.nunique(dropna=True) == 2:
            scoring["roc_auc"] = "roc_auc"
    elif task == "regression":
        y = pd.to_numeric(y, errors="coerce")
        valid = y.notna()
        work = work.loc[valid]
        y = y.loc[valid]
        folds = min(folds, len(y))
        if folds < 2:
            raise ValueError("Regression cross-validation için en az 2 hedef gözlemi gerekli")
        model = RandomForestRegressor(n_estimators=250, random_state=42, n_jobs=-1)
        cv = KFold(n_splits=folds, shuffle=True, random_state=42)
        scoring = {
            "r2": "r2",
            "mae": "neg_mean_absolute_error",
            "rmse": "neg_root_mean_squared_error",
        }
    else:
        raise ValueError("task auto/classification/regression olmalı")
    if len(work) < 8:
        raise ValueError("Model taraması için en az 8 geçerli satır gerekli")
    pipe = Pipeline([("prep", pre), ("model", model)])
    cvres = cross_validate(
        pipe, work, y, cv=cv, scoring=scoring, n_jobs=1, return_train_score=False
    )
    metrics = {
        k.replace("test_", ""): {"mean": float(np.mean(v)), "std": float(np.std(v))}
        for k, v in cvres.items()
        if k.startswith("test_")
    }
    test_size: float | int = 0.25
    if task == "classification":
        test_size = max(int(np.ceil(len(y) * 0.25)), int(y.nunique()))
    Xtr, Xte, ytr, yte = train_test_split(
        work,
        y,
        test_size=test_size,
        random_state=42,
        stratify=y if task == "classification" else None,
    )
    pipe.fit(Xtr, ytr)
    score_name = "accuracy" if task == "classification" else "neg_mean_absolute_error"
    pi = permutation_importance(pipe, Xte, yte, n_repeats=5, random_state=42, scoring=score_name)
    importance = sorted(
        [
            {"feature": c, "importance": float(v)}
            for c, v in zip(predictors, pi.importances_mean, strict=True)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )
    return {
        "task": task,
        "rows": len(work),
        "folds": folds,
        "cv_metrics": metrics,
        "permutation_importance": importance,
        "guardrail": "Baseline predictive screening only. Check leakage, temporal splits, fairness, calibration and business cost before deployment.",
    }


def monte_carlo_npv(
    face_value: float,
    purchase_price: float,
    recovery_rate_mean: float,
    recovery_rate_sd: float,
    months_mean: float,
    months_sd: float,
    annual_discount_rate: float,
    simulations: int = 20000,
) -> dict:
    """Monte Carlo NPL valuation under uncertain recovery rate and timing."""
    values = [
        face_value,
        purchase_price,
        recovery_rate_mean,
        recovery_rate_sd,
        months_mean,
        months_sd,
        annual_discount_rate,
    ]
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Tüm Monte Carlo girdileri sonlu sayı olmalı")
    if face_value < 0 or purchase_price < 0:
        raise ValueError("face_value ve purchase_price negatif olamaz")
    if not 0 <= recovery_rate_mean <= 1 or recovery_rate_sd < 0:
        raise ValueError("Recovery mean 0..1 aralığında, standard deviation negatif olmamalı")
    if months_mean < 0 or months_sd < 0 or annual_discount_rate <= -1:
        raise ValueError("Zaman/iskonto girdileri geçersiz")
    simulations = max(1000, min(int(simulations), 200000))
    rng = np.random.default_rng(42)
    rr = np.clip(rng.normal(recovery_rate_mean, recovery_rate_sd, simulations), 0, 1)
    months = np.clip(rng.normal(months_mean, months_sd, simulations), 0, 360)
    monthly = (1 + annual_discount_rate) ** (1 / 12) - 1
    collections = face_value * rr
    npv = collections / np.power(1 + monthly, months)
    moic = collections / purchase_price if purchase_price > 0 else None
    return {
        "simulations": simulations,
        "npv": {
            "mean": float(np.mean(npv)),
            "median": float(np.median(npv)),
            "p05": float(np.quantile(npv, 0.05)),
            "p95": float(np.quantile(npv, 0.95)),
            "probability_above_purchase_price": float(np.mean(npv > purchase_price))
            if purchase_price
            else None,
        },
        "moic": None
        if moic is None
        else {
            "mean": float(np.mean(moic)),
            "p05": float(np.quantile(moic, 0.05)),
            "p95": float(np.quantile(moic, 0.95)),
        },
        "guardrail": "Distribution assumptions are scenario inputs, not empirical truth. Calibrate from approved historical data.",
    }
