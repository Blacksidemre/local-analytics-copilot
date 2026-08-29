from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import infer_column_roles, load_table, safe_output_path, serializable


def _load(file_path: str, sheet_name: str = "0") -> pd.DataFrame:
    s = get_settings()
    p = resolve_workspace_path(s.workspace, file_path)
    sheet = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    return load_table(p, sheet)


def _finite(x) -> np.ndarray:
    a = pd.to_numeric(pd.Series(x), errors="coerce").to_numpy(dtype=float)
    return a[np.isfinite(a)]


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / max(len(a) + len(b) - 2, 1))
    return 0.0 if pooled == 0 else float((np.mean(a) - np.mean(b)) / pooled)


def _rank_biserial_from_u(u: float, n1: int, n2: int) -> float:
    return float(1 - 2 * u / (n1 * n2))


def _normality(x: np.ndarray) -> dict:
    if len(x) < 3:
        return {"test": "insufficient", "p_value": None, "normalish": False}
    sample = x if len(x) <= 5000 else np.random.default_rng(42).choice(x, 5000, replace=False)
    if len(sample) <= 5000:
        r = stats.shapiro(sample)
        p = float(r.pvalue)
        name = "Shapiro-Wilk"
    else:  # pragma: no cover
        r = stats.normaltest(sample)
        p = float(r.pvalue)
        name = "D'Agostino K2"
    return {
        "test": name,
        "sample_n": len(sample),
        "p_value": p,
        "normalish": p >= 0.05,
        "note": "Normality tests can be over-sensitive; plots, sample size and robustness matter.",
    }


def recommend_analysis(file_path: str, question: str = "", sheet_name: str = "0") -> dict:
    """Recommend a small defensible analysis plan from data roles and a natural-language question."""
    df = _load(file_path, sheet_name)
    roles = infer_column_roles(df)
    q = question.lower()
    plan = []
    if roles["numeric"]:
        plan.append(
            {
                "priority": 1,
                "method": "descriptive_statistics",
                "why": "Numeric variables exist; establish scale, spread, missingness and outliers first.",
            }
        )
    if len(roles["numeric"]) >= 2:
        plan.append(
            {
                "priority": 2,
                "method": "correlation",
                "why": "Multiple numeric variables allow association screening; correlation is not causality.",
            }
        )
    if roles["numeric"] and roles["categorical"]:
        plan.append(
            {
                "priority": 2,
                "method": "group_comparison",
                "why": "Numeric outcome can be compared across categorical segments; method depends on number of groups and assumptions.",
            }
        )
    if len(roles["categorical"]) >= 2:
        plan.append(
            {
                "priority": 3,
                "method": "categorical_association",
                "why": "Categorical variables can be assessed with contingency-table methods.",
            }
        )
    if roles["datetime"] and roles["numeric"]:
        plan.append(
            {
                "priority": 2,
                "method": "time_series_or_trend",
                "why": "A date/time column plus numeric metric supports trend and forecasting checks.",
            }
        )
    if any(k in q for k in ["tahmin", "forecast", "gelecek"]):
        plan.insert(
            0,
            {
                "priority": 1,
                "method": "forecasting",
                "why": "Question explicitly asks for future estimates; validate time order and backtest.",
            },
        )
    if any(k in q for k in ["anomali", "aykırı", "fraud", "şüphe"]):
        plan.insert(
            0,
            {
                "priority": 1,
                "method": "anomaly_detection",
                "why": "Question explicitly asks for unusual observations; use multi-signal flags and human review.",
            },
        )
    if any(k in q for k in ["etki", "neden", "açıkla", "driver", "sürücü"]):
        plan.append(
            {
                "priority": 2,
                "method": "regression",
                "why": "Regression can quantify conditional associations, but causal language requires stronger design.",
            }
        )
    return {
        "roles": roles,
        "recommended_plan": plan[:8],
        "guardrail": "Recommendations are a starting plan; business definitions and study design can change the correct method.",
    }


def descriptive_analysis(
    file_path: str, columns: list[str] | None = None, sheet_name: str = "0"
) -> dict:
    df = _load(file_path, sheet_name)
    cols = columns or infer_column_roles(df)["numeric"]
    result = {}
    for c in cols:
        if c not in df:
            continue
        x = _finite(df[c])
        if not len(x):
            continue
        sem = stats.sem(x) if len(x) > 1 else np.nan
        ci = (
            stats.t.interval(0.95, len(x) - 1, loc=np.mean(x), scale=sem)
            if len(x) > 1 and np.isfinite(sem)
            else (np.nan, np.nan)
        )
        result[c] = {
            "n": len(x),
            "mean": float(np.mean(x)),
            "median": float(np.median(x)),
            "std": float(np.std(x, ddof=1)) if len(x) > 1 else None,
            "min": float(np.min(x)),
            "q1": float(np.quantile(x, 0.25)),
            "q3": float(np.quantile(x, 0.75)),
            "max": float(np.max(x)),
            "skew": float(stats.skew(x, bias=False)) if len(x) > 2 else None,
            "mean_95ci": [serializable(ci[0]), serializable(ci[1])],
            "normality": _normality(x),
        }
    return {"columns": result}


def compare_two_groups(
    file_path: str,
    value_column: str,
    group_column: str,
    group_a: str,
    group_b: str,
    sheet_name: str = "0",
) -> dict:
    """Compare two independent groups using Welch t-test or Mann-Whitney U after diagnostics."""
    s = get_settings()
    df = _load(file_path, sheet_name)
    if value_column not in df or group_column not in df:
        raise KeyError("Belirtilen kolonlardan biri bulunamadı")
    groups = df[group_column].astype(str)
    vals = pd.to_numeric(df[value_column], errors="coerce")
    a = _finite(vals[groups.eq(str(group_a))])
    b = _finite(vals[groups.eq(str(group_b))])
    if len(a) < 3 or len(b) < 3:
        raise ValueError("Her grup için en az 3 geçerli gözlem gerekli")
    na, nb = _normality(a), _normality(b)
    normalish = na["normalish"] and nb["normalish"]
    if normalish:
        test = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
        method = "Welch independent-samples t-test"
        effect = {"name": "Cohen's d", "value": _cohens_d(a, b)}
    else:
        test = stats.mannwhitneyu(a, b, alternative="two-sided")
        method = "Mann-Whitney U"
        effect = {
            "name": "rank-biserial correlation (orientation depends on group order)",
            "value": _rank_biserial_from_u(float(test.statistic), len(a), len(b)),
        }
    res = {
        "method": method,
        "group_a": {
            "name": group_a,
            "n": len(a),
            "mean": float(np.mean(a)),
            "median": float(np.median(a)),
        },
        "group_b": {
            "name": group_b,
            "n": len(b),
            "mean": float(np.mean(b)),
            "median": float(np.median(b)),
        },
        "normality": {"a": na, "b": nb},
        "statistic": float(test.statistic),
        "p_value": float(test.pvalue),
        "effect_size": effect,
        "guardrail": "Statistical significance and business significance are different. Non-randomized data do not establish causality.",
    }
    audit(s.logs_dir, "compare_two_groups", file=file_path, method=method, p_value=res["p_value"])
    return res


def compare_multiple_groups(
    file_path: str, value_column: str, group_column: str, sheet_name: str = "0"
) -> dict:
    """Compare 3+ independent groups using ANOVA, Welch ANOVA, or Kruskal-Wallis."""
    df = _load(file_path, sheet_name)
    work = df[[value_column, group_column]].copy()
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
    work = work.dropna()
    labels = [str(x) for x in work[group_column].unique()]
    arrays = [
        work.loc[work[group_column].astype(str) == g, value_column].to_numpy(dtype=float)
        for g in labels
    ]
    arrays = [a for a in arrays if len(a) >= 3]
    labels = [g for g in labels if len(work.loc[work[group_column].astype(str) == g]) >= 3]
    if len(arrays) < 3:
        raise ValueError("En az 3 grup ve grup başına en az 3 gözlem gerekli")
    normal = all(_normality(a)["normalish"] for a in arrays)
    levene = float(stats.levene(*arrays, center="median").pvalue)
    eligible = work[work[group_column].astype(str).isin(labels)]
    total = np.concatenate(arrays)
    grand_mean = float(np.mean(total))
    between = sum(len(a) * (float(np.mean(a)) - grand_mean) ** 2 for a in arrays)
    total_ss = float(np.sum((total - grand_mean) ** 2))
    eta_squared = between / total_ss if total_ss else 0.0
    if normal and levene >= 0.05:
        t = stats.f_oneway(*arrays)
        method = "One-way ANOVA"
        posthoc = []
        try:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd

            tuk = pairwise_tukeyhsd(eligible[value_column], eligible[group_column].astype(str))
            posthoc = [
                {
                    "group1": str(r[0]),
                    "group2": str(r[1]),
                    "mean_diff": float(r[2]),
                    "p_adj": float(r[3]),
                    "reject": bool(r[6]),
                }
                for r in tuk._results_table.data[1:]
            ]
        except Exception:
            posthoc = []
        effect_size = {"name": "eta_squared", "value": float(eta_squared)}
    elif normal:
        from statsmodels.stats.oneway import anova_oneway

        t = anova_oneway(arrays, use_var="unequal", welch_correction=True)
        method = "Welch ANOVA"
        posthoc = []
        effect_size = {"name": "eta_squared_descriptive", "value": float(eta_squared)}
    else:
        t = stats.kruskal(*arrays)
        method = "Kruskal-Wallis"
        posthoc = []
        epsilon = max(0.0, (float(t.statistic) - len(arrays) + 1) / (len(total) - len(arrays)))
        effect_size = {"name": "epsilon_squared", "value": float(epsilon)}
    return {
        "method": method,
        "groups": [
            {"group": g, "n": len(a), "mean": float(np.mean(a)), "median": float(np.median(a))}
            for g, a in zip(labels, arrays, strict=True)
        ],
        "normality_all_passed": normal,
        "levene_p": levene,
        "statistic": float(t.statistic),
        "p_value": float(t.pvalue),
        "effect_size": effect_size,
        "posthoc": posthoc,
        "guardrail": "If the omnibus test is significant, pairwise interpretation should control multiple comparisons.",
    }


def categorical_association(
    file_path: str, column_a: str, column_b: str, sheet_name: str = "0"
) -> dict:
    df = _load(file_path, sheet_name)
    table = pd.crosstab(df[column_a], df[column_b])
    if table.empty:
        raise ValueError("Kontenjans tablosu boş")
    chi2, p, dof, expected = stats.chi2_contingency(table)
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    cramer = math.sqrt(chi2 / (n * k)) if n > 0 and k > 0 else None
    low_expected = float((expected < 5).mean())
    method = "Chi-square"
    fisher = None
    if table.shape == (2, 2) and low_expected > 0:
        odds, fp = stats.fisher_exact(table.to_numpy())
        fisher = {"odds_ratio": float(odds), "p_value": float(fp)}
        method = "Chi-square + Fisher exact check"
    return {
        "method": method,
        "table": table.to_dict(),
        "chi2": float(chi2),
        "p_value": float(p),
        "dof": int(dof),
        "cramers_v": cramer,
        "expected_cells_below_5_pct": round(low_expected * 100, 2),
        "fisher": fisher,
    }


def correlation_analysis(
    file_path: str, columns: list[str], method: str = "spearman", sheet_name: str = "0"
) -> dict:
    if method not in {"pearson", "spearman", "kendall"}:
        raise ValueError("method pearson/spearman/kendall olmalı")
    df = _load(file_path, sheet_name)
    missing = [c for c in columns if c not in df]
    if missing:
        raise KeyError(f"Kolonlar bulunamadı: {missing}")
    matrix = df[columns].apply(pd.to_numeric, errors="coerce").corr(method=method).round(6)
    pairs = []
    for i, a in enumerate(columns):
        for b in columns[i + 1 :]:
            sub = df[[a, b]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(sub) < 3:
                continue
            if method == "pearson":
                r, p = stats.pearsonr(sub[a], sub[b])
            elif method == "spearman":
                r, p = stats.spearmanr(sub[a], sub[b])
            else:
                r, p = stats.kendalltau(sub[a], sub[b])
            pairs.append({"a": a, "b": b, "r": float(r), "p_value": float(p), "n": len(sub)})
    return {
        "method": method,
        "matrix": matrix.to_dict(),
        "pairs": pairs,
        "warning": "Correlation does not establish causality.",
    }


def linear_regression(
    file_path: str, target: str, predictors: list[str], sheet_name: str = "0"
) -> dict:
    """OLS regression with basic diagnostics. Categorical predictors should be pre-encoded or use logistic/other workflows."""
    import statsmodels.api as sm

    df = _load(file_path, sheet_name)
    cols = [target] + predictors
    work = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(work) < max(20, len(predictors) * 5):
        raise ValueError("Regression için yeterli complete-case gözlem yok")
    X = sm.add_constant(work[predictors], has_constant="add")
    y = work[target]
    model = sm.OLS(y, X).fit()
    from statsmodels.stats.diagnostic import het_breuschpagan

    bp = het_breuschpagan(model.resid, model.model.exog)
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor

        vifs = {
            name: float(variance_inflation_factor(X.to_numpy(), i))
            for i, name in enumerate(X.columns)
            if name != "const"
        }
    except Exception:
        vifs = {}
    coeff = []
    ci = model.conf_int()
    for name, val in model.params.items():
        coeff.append(
            {
                "term": name,
                "coef": float(val),
                "p_value": float(model.pvalues[name]),
                "ci95": [float(ci.loc[name, 0]), float(ci.loc[name, 1])],
            }
        )
    return {
        "n": int(model.nobs),
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "f_p_value": float(model.f_pvalue),
        "coefficients": coeff,
        "breusch_pagan_p": float(bp[1]),
        "vif": vifs,
        "aic": float(model.aic),
        "bic": float(model.bic),
        "guardrail": "OLS estimates conditional association. Check design, nonlinearity, influential points and omitted variables before causal interpretation.",
    }


def logistic_regression(
    file_path: str,
    target: str,
    predictors: list[str],
    positive_value: str = "1",
    sheet_name: str = "0",
) -> dict:
    import statsmodels.api as sm
    from sklearn.metrics import roc_auc_score

    df = _load(file_path, sheet_name)
    y = df[target].astype(str).eq(str(positive_value)).astype(int)
    X = df[predictors].apply(pd.to_numeric, errors="coerce")
    work = pd.concat([y.rename("_y"), X], axis=1).dropna()
    y = work.pop("_y")
    if y.nunique() != 2:
        raise ValueError("Binary target iki sınıf içermeli")
    X = sm.add_constant(work, has_constant="add")
    model = sm.Logit(y, X).fit(disp=False, maxiter=200)
    pred = model.predict(X)
    ci = model.conf_int()
    rows = []
    for name, val in model.params.items():
        rows.append(
            {
                "term": name,
                "log_odds": float(val),
                "odds_ratio": float(np.exp(val)),
                "p_value": float(model.pvalues[name]),
                "or_ci95": [float(np.exp(ci.loc[name, 0])), float(np.exp(ci.loc[name, 1]))],
            }
        )
    return {
        "n": int(model.nobs),
        "pseudo_r2": float(model.prsquared),
        "auc_in_sample": float(roc_auc_score(y, pred)),
        "coefficients": rows,
        "aic": float(model.aic),
        "guardrail": "In-sample AUC is optimistic. Use train/test or cross-validation for predictive claims.",
    }


def pca_analysis(
    file_path: str, columns: list[str], n_components: int = 2, sheet_name: str = "0"
) -> dict:
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    if not columns:
        raise ValueError("PCA için en az bir kolon gerekli")
    df = _load(file_path, sheet_name)
    X = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 2:
        raise ValueError("PCA için en az 2 complete-case satır gerekli")
    n_components = max(1, min(n_components, len(columns), len(X)))
    Z = StandardScaler().fit_transform(X)
    p = PCA(n_components=n_components).fit(Z)
    loadings = pd.DataFrame(
        p.components_.T, index=columns, columns=[f"PC{i + 1}" for i in range(n_components)]
    )
    return {
        "n": len(X),
        "explained_variance_ratio": [float(x) for x in p.explained_variance_ratio_],
        "cumulative_variance": [float(x) for x in np.cumsum(p.explained_variance_ratio_)],
        "loadings": loadings.round(6).to_dict(),
    }


def cluster_analysis(
    file_path: str, columns: list[str], n_clusters: int = 3, sheet_name: str = "0"
) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    if not columns:
        raise ValueError("Clustering için en az bir kolon gerekli")
    df = _load(file_path, sheet_name)
    X = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 3:
        raise ValueError("Clustering için en az 3 complete-case satır gerekli")
    n_clusters = max(2, min(n_clusters, len(X) - 1, 20))
    Z = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=n_clusters, n_init=20, random_state=42).fit(Z)
    labels = km.labels_
    sil = float(silhouette_score(Z, labels)) if len(set(labels)) > 1 else None
    tmp = X.copy()
    tmp["cluster"] = labels
    profiles = tmp.groupby("cluster").agg(["mean", "median", "count"])
    return {
        "n": len(X),
        "clusters": n_clusters,
        "silhouette": sil,
        "cluster_sizes": pd.Series(labels).value_counts().sort_index().to_dict(),
        "profiles": {
            str(k): {str(a): serializable(b) for a, b in row.items()}
            for k, row in profiles.iterrows()
        },
    }


def anomaly_detection(
    file_path: str,
    columns: list[str],
    contamination: float = 0.01,
    sheet_name: str = "0",
    output_name: str = "anomalies.csv",
) -> dict:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import RobustScaler

    s = get_settings()
    df = _load(file_path, sheet_name)
    X = df[columns].apply(pd.to_numeric, errors="coerce")
    complete = X.dropna()
    contamination = max(0.001, min(float(contamination), 0.2))
    if len(complete) < 20:
        raise ValueError("Anomaly detection için en az 20 complete-case satır önerilir")
    Z = RobustScaler().fit_transform(complete)
    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=200).fit(Z)
    score = -model.score_samples(Z)
    pred = model.predict(Z)
    flagged = complete.copy()
    flagged["anomaly_score"] = score
    flagged["is_anomaly"] = pred == -1
    flagged = flagged[flagged["is_anomaly"]].sort_values("anomaly_score", ascending=False)
    output = safe_output_path(output_name, ".csv")
    flagged.to_csv(output, index=True)
    return {
        "rows_analyzed": len(complete),
        "anomalies": len(flagged),
        "contamination": contamination,
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "top_anomalies": flagged.head(20).reset_index().to_dict(orient="records"),
        "guardrail": "Anomalies are review candidates, not proof of fraud or error.",
    }


def time_series_forecast(
    file_path: str,
    date_column: str,
    value_column: str,
    periods: int = 6,
    frequency: str = "MS",
    sheet_name: str = "0",
) -> dict:
    """Aggregate a numeric metric by period and fit Holt-Winters exponential smoothing with a holdout backtest."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    allowed_frequencies = {"D", "W", "MS", "ME", "QS", "QE", "YS", "YE"}
    frequency = frequency.upper()
    if frequency not in allowed_frequencies:
        raise ValueError(f"frequency şunlardan biri olmalı: {sorted(allowed_frequencies)}")
    df = _load(file_path, sheet_name)
    work = df[[date_column, value_column]].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
    work = work.dropna().sort_values(date_column)
    ts = work.set_index(date_column)[value_column].resample(frequency).sum().astype(float)
    if len(ts) < 8:
        raise ValueError("Forecast için en az 8 zaman periyodu gerekli")
    hold = max(1, min(3, len(ts) // 4))
    train, test = ts.iloc[:-hold], ts.iloc[-hold:]
    seasonal = "add" if len(train) >= 24 and frequency.upper().startswith("M") else None
    sp = 12 if seasonal else None
    fit = ExponentialSmoothing(
        train,
        trend="add",
        seasonal=seasonal,
        seasonal_periods=sp,
        initialization_method="estimated",
    ).fit(optimized=True)
    pred = fit.forecast(hold)
    mae = float(np.mean(np.abs(test.to_numpy() - pred.to_numpy())))
    mape = float(
        np.mean(
            np.abs(
                (test.to_numpy() - pred.to_numpy())
                / np.where(test.to_numpy() == 0, np.nan, test.to_numpy())
            )
        )
        * 100
    )
    final = ExponentialSmoothing(
        ts, trend="add", seasonal=seasonal, seasonal_periods=sp, initialization_method="estimated"
    ).fit(optimized=True)
    fc = final.forecast(max(1, min(periods, 36)))
    return {
        "observations": len(ts),
        "frequency": frequency,
        "backtest": {"holdout": hold, "mae": mae, "mape_pct": None if np.isnan(mape) else mape},
        "forecast": [{"period": str(i), "value": float(v)} for i, v in fc.items()],
        "guardrail": "Forecasts extrapolate historical patterns; structural breaks and policy/process changes can invalidate them.",
    }


def survival_analysis(
    file_path: str,
    duration_column: str,
    event_column: str,
    group_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Kaplan-Meier survival summary. Requires optional `lifelines` package."""
    try:
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test
    except ImportError as exc:
        raise RuntimeError(
            "Survival analysis için `pip install -e '.[survival]'` çalıştırın"
        ) from exc
    df = _load(file_path, sheet_name)
    duration = pd.to_numeric(df[duration_column], errors="coerce")
    event = pd.to_numeric(df[event_column], errors="coerce").fillna(0).astype(int)
    valid = duration.notna() & event.isin([0, 1])
    work = df.loc[valid].copy()
    work[duration_column] = duration[valid]
    work[event_column] = event[valid]
    if not group_column:
        km = KaplanMeierFitter().fit(work[duration_column], event_observed=work[event_column])
        return {
            "n": len(work),
            "events": int(work[event_column].sum()),
            "median_survival": serializable(km.median_survival_time_),
            "timeline": [
                {"t": float(t), "survival": float(v)}
                for t, v in km.survival_function_.iloc[:: max(1, len(km.survival_function_) // 50)]
                .iloc[:, 0]
                .items()
            ],
        }
    groups = [str(g) for g in work[group_column].dropna().unique()]
    summaries = []
    for g in groups:
        sub = work[work[group_column].astype(str) == g]
        km = KaplanMeierFitter().fit(sub[duration_column], event_observed=sub[event_column])
        summaries.append(
            {
                "group": g,
                "n": len(sub),
                "events": int(sub[event_column].sum()),
                "median_survival": serializable(km.median_survival_time_),
            }
        )
    logrank = None
    if len(groups) == 2:
        a = work[work[group_column].astype(str) == groups[0]]
        b = work[work[group_column].astype(str) == groups[1]]
        lr = logrank_test(
            a[duration_column],
            b[duration_column],
            event_observed_A=a[event_column],
            event_observed_B=b[event_column],
        )
        logrank = {"p_value": float(lr.p_value), "test_statistic": float(lr.test_statistic)}
    return {
        "groups": summaries,
        "logrank": logrank,
        "guardrail": "Censoring assumptions and event definitions must match the business process.",
    }
