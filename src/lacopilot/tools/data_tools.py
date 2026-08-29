from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import (
    infer_column_roles,
    load_table,
    safe_excel_writer,
    safe_output_path,
    serializable,
)


def _sheet_arg(sheet_name: str):
    return int(sheet_name) if str(sheet_name).isdigit() else sheet_name


def list_workspace_files(folder: str = "incoming") -> dict:
    """List supported local files inside a workspace folder."""
    s = get_settings()
    path = resolve_workspace_path(s.workspace, folder)
    if not path.exists():
        return {"files": [], "count": 0}
    allowed = {
        ".csv",
        ".xlsx",
        ".xlsm",
        ".xls",
        ".parquet",
        ".json",
        ".jsonl",
        ".pdf",
        ".docx",
        ".txt",
        ".md",
    }
    items = []
    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in allowed:
            items.append(
                {
                    "path": str(p.resolve().relative_to(s.workspace.resolve())),
                    "type": p.suffix.lower(),
                    "size_mb": round(p.stat().st_size / 1024**2, 3),
                }
            )
    return {"files": items[:1000], "count": len(items)}


def inspect_dataset(file_path: str, sheet_name: str = "0", sample_rows: int = 5) -> dict:
    """Inspect a local dataset and return schema + a tiny sample."""
    s = get_settings()
    path = resolve_workspace_path(s.workspace, file_path)
    if not path.exists():
        raise FileNotFoundError(path)
    df = load_table(path, _sheet_arg(sheet_name))
    roles = infer_column_roles(df)
    result = {
        "file": str(path.resolve().relative_to(s.workspace.resolve())),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "column_names": list(map(str, df.columns)),
        "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
        "roles": roles,
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1024**2, 2),
        "sample": [
            {str(k): serializable(v) for k, v in row.items()}
            for row in df.head(max(0, min(sample_rows, 20))).to_dict(orient="records")
        ],
    }
    audit(
        s.logs_dir,
        "inspect_dataset",
        file=file_path,
        rows=result["rows"],
        columns=result["columns"],
    )
    return result


def _robust_outlier_counts(x: pd.Series) -> dict:
    y = pd.to_numeric(x, errors="coerce").dropna()
    if len(y) < 5:
        return {"iqr": 0, "robust_z": 0}
    q1, q3 = y.quantile([0.25, 0.75])
    iqr = q3 - q1
    iqr_n = int(((y < q1 - 1.5 * iqr) | (y > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    med = float(y.median())
    mad = float(np.median(np.abs(y - med)))
    rz_n = int((np.abs(0.6745 * (y - med) / mad) > 3.5).sum()) if mad > 0 else 0
    return {"iqr": iqr_n, "robust_z": rz_n}


def profile_dataset(file_path: str, sheet_name: str = "0") -> dict:
    """Create a descriptive and data-quality profile; never deletes or mutates source data."""
    s = get_settings()
    path = resolve_workspace_path(s.workspace, file_path)
    df = load_table(path, _sheet_arg(sheet_name))
    n = max(len(df), 1)
    m = max(df.shape[1], 1)
    missing = df.isna().sum().sort_values(ascending=False)
    missing_pct = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    duplicate_rows = int(df.duplicated().sum())
    roles = infer_column_roles(df)
    numeric_summary = {}
    outliers = {}
    for col in roles["numeric"][:100]:
        x = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(x):
            numeric_summary[col] = {
                "count": int(len(x)),
                "mean": serializable(x.mean()),
                "median": serializable(x.median()),
                "std": serializable(x.std()),
                "min": serializable(x.min()),
                "q1": serializable(x.quantile(0.25)),
                "q3": serializable(x.quantile(0.75)),
                "max": serializable(x.max()),
                "skew": serializable(x.skew()),
            }
            outliers[col] = _robust_outlier_counts(x)
    categorical_summary = {}
    for col in roles["categorical"][:100]:
        vc = df[col].astype("string").value_counts(dropna=False).head(10)
        categorical_summary[col] = {str(k): int(v) for k, v in vc.items()}
    total_cells = n * m
    missing_rate = float(df.isna().sum().sum()) / total_cells
    duplicate_rate = duplicate_rows / n
    constant = [str(c) for c in df.columns if df[c].nunique(dropna=False) <= 1]
    quality_score = 100.0
    quality_score -= min(35, missing_rate * 100 * 0.8)
    quality_score -= min(20, duplicate_rate * 100)
    quality_score -= min(15, len(constant) / m * 100 * 0.5)
    quality_score = max(0.0, quality_score)
    result = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "roles": roles,
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round(duplicate_rate * 100, 3),
        "quality_score_heuristic": round(quality_score, 2),
        "missing_count": {str(k): int(v) for k, v in missing.items()},
        "missing_pct": {str(k): float(v) for k, v in missing_pct.items()},
        "constant_columns": constant,
        "high_missing_columns": [str(c) for c, p in missing_pct.items() if p >= 20],
        "numeric_summary": numeric_summary,
        "categorical_top_values": categorical_summary,
        "outlier_flags": outliers,
        "notes": [
            "Quality score is a screening heuristic, not an audit opinion.",
            "Outliers are flagged for review; they are not automatically removed.",
            "Identifier columns are excluded from most numeric analysis recommendations.",
        ],
    }
    audit(
        s.logs_dir,
        "profile_dataset",
        file=file_path,
        quality_score=result["quality_score_heuristic"],
    )
    return result


def compare_schemas(file_a: str, file_b: str, sheet_a: str = "0", sheet_b: str = "0") -> dict:
    """Compare two dataset schemas to detect schema drift."""
    s = get_settings()
    a = load_table(resolve_workspace_path(s.workspace, file_a), _sheet_arg(sheet_a), nrows=1000)
    b = load_table(resolve_workspace_path(s.workspace, file_b), _sheet_arg(sheet_b), nrows=1000)
    ca, cb = set(map(str, a.columns)), set(map(str, b.columns))
    common = sorted(ca & cb)
    dtype_changes = []
    for c in common:
        da, db = str(a[c].dtype), str(b[c].dtype)
        if da != db:
            dtype_changes.append({"column": c, "from": da, "to": db})
    return {
        "added_columns": sorted(cb - ca),
        "removed_columns": sorted(ca - cb),
        "dtype_changes": dtype_changes,
        "common_columns": common,
        "schema_drift_detected": bool((cb - ca) or (ca - cb) or dtype_changes),
    }


def validate_data_quality(file_path: str, rules_json: str, sheet_name: str = "0") -> dict:
    """Evaluate explicit data-quality rules from a JSON list; does not modify data.

    Supported rule types: not_null, min, max, between, unique, allowed_values.
    """
    s = get_settings()
    df = load_table(resolve_workspace_path(s.workspace, file_path), _sheet_arg(sheet_name))
    rules = json.loads(rules_json)
    if not isinstance(rules, list):
        raise ValueError("rules_json must contain a JSON list")
    results = []
    for r in rules:
        col = r.get("column")
        typ = r.get("type")
        name = r.get("name") or f"{col}_{typ}"
        if col not in df.columns:
            results.append(
                {"name": name, "passed": False, "violations": len(df), "error": "column_not_found"}
            )
            continue
        x = df[col]
        if typ == "not_null":
            bad = x.isna()
        elif typ == "min":
            y = pd.to_numeric(x, errors="coerce")
            bad = (y.isna() & x.notna()) | (y < float(r["value"]))
        elif typ == "max":
            y = pd.to_numeric(x, errors="coerce")
            bad = (y.isna() & x.notna()) | (y > float(r["value"]))
        elif typ == "between":
            y = pd.to_numeric(x, errors="coerce")
            bad = (y.isna() & x.notna()) | (y < float(r["min"])) | (y > float(r["max"]))
        elif typ == "unique":
            bad = x.duplicated(keep=False)
        elif typ == "allowed_values":
            bad = ~x.isin(r.get("values", [])) & x.notna()
        else:
            raise ValueError(f"Unsupported rule type: {typ}")
        cnt = int(bad.fillna(False).sum())
        results.append(
            {
                "name": name,
                "column": col,
                "type": typ,
                "severity": r.get("severity", "warning"),
                "passed": cnt == 0,
                "violations": cnt,
                "violation_pct": round(cnt / max(len(df), 1) * 100, 3),
            }
        )
    critical = [r for r in results if not r["passed"] and r.get("severity") == "critical"]
    return {
        "rows": len(df),
        "passed": not critical,
        "rules": results,
        "critical_failures": len(critical),
    }


def cleaning_plan(file_path: str, sheet_name: str = "0") -> dict:
    """Generate a safe cleaning proposal. It never edits the source file."""
    p = profile_dataset(file_path, sheet_name)
    actions = []
    if p["duplicate_rows"]:
        actions.append(
            {"action": "review_duplicates", "count": p["duplicate_rows"], "automatic": False}
        )
    for col, pct in p["missing_pct"].items():
        if pct > 0:
            suggestion = (
                "investigate_source"
                if pct >= 20
                else "consider_domain_based_imputation_or_keep_missing"
            )
            actions.append(
                {"column": col, "action": suggestion, "missing_pct": pct, "automatic": False}
            )
    for col, counts in p["outlier_flags"].items():
        if counts["iqr"] or counts["robust_z"]:
            actions.append(
                {"column": col, "action": "review_outliers", **counts, "automatic": False}
            )
    return {
        "file": file_path,
        "proposed_actions": actions,
        "source_mutated": False,
        "rule": "Cleaning changes should be previewed and written to a new processed file after approval.",
    }


def generate_synthetic_dataset(
    file_path: str,
    output_name: str = "synthetic_data.csv",
    rows: int = 1000,
    sheet_name: str = "0",
    random_state: int = 42,
    preserve_categories: bool = False,
) -> dict:
    """Generate a simple local synthetic/bootstrapped dataset for testing.

    This is NOT a formal privacy guarantee. It deliberately avoids copying identifier-like columns.
    Numeric columns are resampled with noise; categorical columns use empirical frequencies.
    """
    s = get_settings()
    df = load_table(resolve_workspace_path(s.workspace, file_path), _sheet_arg(sheet_name))
    roles = infer_column_roles(df)
    rng = np.random.default_rng(random_state)
    rows = max(10, min(int(rows), 1_000_000))
    out = pd.DataFrame(index=np.arange(rows))
    for col in df.columns:
        name = str(col)
        x = df[col]
        if name in roles["identifier"]:
            out[name] = [f"SYN_{i + 1:08d}" for i in range(rows)]
        elif name in roles["numeric"]:
            vals = pd.to_numeric(x, errors="coerce").dropna().to_numpy(dtype=float)
            if not len(vals):
                out[name] = np.nan
                continue
            sample = rng.choice(vals, size=rows, replace=True)
            scale = np.nanstd(vals) * 0.03
            out[name] = sample + (rng.normal(0, scale, rows) if scale > 0 else 0)
        elif name in roles["datetime"]:
            vals = pd.to_datetime(x, errors="coerce").dropna()
            if len(vals):
                sampled = pd.to_datetime(rng.choice(vals.to_numpy(), rows, replace=True))
                out[name] = sampled + pd.to_timedelta(rng.integers(-14, 15, rows), unit="D")
            else:
                out[name] = pd.NaT
        elif name in roles["text"]:
            out[name] = [f"TEXT_{value:08d}" for value in rng.integers(1, 10**8, rows)]
        else:
            vals = x.dropna().astype(str)
            if len(vals):
                probs = vals.value_counts(normalize=True)
                labels = (
                    probs.index.to_numpy()
                    if preserve_categories
                    else np.asarray([f"CAT_{index + 1:03d}" for index in range(len(probs))])
                )
                out[name] = rng.choice(labels, rows, p=probs.to_numpy())
            else:
                out[name] = None
    suffix = ".xlsx" if Path(output_name).suffix.lower() == ".xlsx" else ".csv"
    output = safe_output_path(output_name, suffix)
    if output.suffix.lower() == ".xlsx":
        with safe_excel_writer(output) as writer:
            out.to_excel(writer, index=False)
    else:
        out.to_csv(output, index=False)
    return {
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "rows": rows,
        "categories_preserved": preserve_categories,
        "privacy_warning": "Synthetic output is for testing only. It has not passed formal disclosure-risk or differential-privacy tests; do not treat it as anonymous data.",
    }


def query_dataset_sql(
    file_path: str, sql: str, sheet_name: str = "0", max_rows: int = 5000
) -> dict:
    """Run a read-only SQL query against one local dataset exposed as table `data`.

    Example: SELECT portfolio, SUM(balance) AS balance FROM data GROUP BY portfolio ORDER BY balance DESC
    Requires optional DuckDB package (`pip install -e '.[fast]'`).
    """
    from lacopilot.security import validate_dataset_sql

    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "Dataset SQL için optional dependency gerekli: pip install -e '.[fast]'"
        ) from exc
    s = get_settings()
    path = resolve_workspace_path(s.workspace, file_path)
    safe = validate_dataset_sql(sql)
    limit = max(1, min(int(max_rows), s.max_query_rows, 50_000))
    dataframe = load_table(path, _sheet_arg(sheet_name))
    connection = duckdb.connect(
        database=":memory:",
        config={"enable_external_access": "false", "allow_unsigned_extensions": "false"},
    )
    try:
        connection.register("data", dataframe)
        cursor = connection.execute(safe)
        cols = [description[0] for description in cursor.description]
        rows = cursor.fetchmany(limit + 1)
        truncated = len(rows) > limit
        rows = rows[:limit]
        result = [
            {column: serializable(value) for column, value in zip(cols, row, strict=True)}
            for row in rows
        ]
    finally:
        connection.close()
    audit(
        s.logs_dir,
        "query_dataset_sql",
        file=file_path,
        sql=safe[:1500],
        rows=len(result),
        truncated=truncated,
    )
    return {
        "columns": cols,
        "rows": result,
        "row_count": len(result),
        "truncated": truncated,
        "table_name": "data",
    }
