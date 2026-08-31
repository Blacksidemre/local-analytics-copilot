from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from lacopilot.config import get_settings
from lacopilot.ingestion import read_table


def load_table(
    path: Path,
    sheet_name: str | int | None = 0,
    nrows: int | None = None,
) -> pd.DataFrame:
    return read_table(path, sheet_name=sheet_name, nrows=nrows).dataframe


def safe_output_path(name: str, suffix: str) -> Path:
    settings = get_settings()
    filename = Path(name).name
    if not filename.lower().endswith(suffix.lower()):
        filename += suffix
    candidate = settings.outputs_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    for index in range(2, 10000):
        versioned = candidate.with_name(f"{stem}_{index}{candidate.suffix}")
        if not versioned.exists():
            return versioned
    raise FileExistsError(f"Çıktı için boş sürüm adı bulunamadı: {candidate.name}")


def safe_excel_writer(path: Path) -> pd.ExcelWriter:
    return pd.ExcelWriter(
        path,
        engine="xlsxwriter",
        engine_kwargs={
            "options": {
                "strings_to_formulas": False,
                "strings_to_urls": False,
                "nan_inf_to_errors": True,
            }
        },
    )


def parse_datetime_series(series: pd.Series) -> pd.Series:
    """Parse dates without treating ISO year-first values as day-first dates."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    text = series.astype("string").str.strip()
    iso_mask = text.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\D|$)", na=False)
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if iso_mask.any():
        parsed.loc[iso_mask] = pd.to_datetime(
            text.loc[iso_mask],
            errors="coerce",
            format="mixed",
            yearfirst=True,
            dayfirst=False,
        )
    if (~iso_mask).any():
        parsed.loc[~iso_mask] = pd.to_datetime(
            text.loc[~iso_mask],
            errors="coerce",
            format="mixed",
            dayfirst=True,
        )
    return parsed


def serializable(value: Any):
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return value


def infer_column_roles(df: pd.DataFrame) -> dict[str, list[str]]:
    roles = {
        "numeric": [],
        "categorical": [],
        "datetime": [],
        "identifier": [],
        "text": [],
        "boolean": [],
    }
    row_count = max(len(df), 1)
    for column in df.columns:
        series = df[column]
        name = str(column)
        if pd.api.types.is_bool_dtype(series):
            roles["boolean"].append(name)
            continue
        if pd.api.types.is_datetime64_any_dtype(series):
            roles["datetime"].append(name)
            continue
        if pd.api.types.is_numeric_dtype(series):
            unique_ratio = series.nunique(dropna=True) / row_count
            if unique_ratio > 0.95 and any(
                key in name.lower() for key in ["id", "no", "num", "key"]
            ):
                roles["identifier"].append(name)
            else:
                roles["numeric"].append(name)
            continue
        nonnull = series.dropna().astype(str)
        unique = nonnull.nunique()
        unique_ratio = unique / row_count
        if len(nonnull) and any(key in name.lower() for key in ["date", "tarih", "time", "zaman"]):
            parsed = parse_datetime_series(nonnull.head(500))
            if parsed.notna().mean() > 0.8:
                roles["datetime"].append(name)
                continue
        if unique_ratio > 0.95 and any(key in name.lower() for key in ["id", "no", "code", "kod"]):
            roles["identifier"].append(name)
        elif unique <= 50 or unique_ratio <= 0.05:
            roles["categorical"].append(name)
        else:
            roles["text"].append(name)
    return roles
