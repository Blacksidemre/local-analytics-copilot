from __future__ import annotations

import json

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


def _load(file_path: str, sheet_name: str = "0") -> pd.DataFrame:
    s = get_settings()
    path = resolve_workspace_path(s.workspace, file_path)
    sheet = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    return load_table(path, sheet)


def pivot_analysis(
    file_path: str,
    index_columns: list[str],
    value_columns: list[str],
    aggfunc: str = "sum",
    column_columns: list[str] | None = None,
    filters_json: str = "{}",
    sheet_name: str = "0",
    output_name: str = "pivot_report.xlsx",
) -> dict:
    """Create a deterministic pivot/aggregation and export it to Excel.

    `aggfunc` may be sum, mean, median, count, min, max, nunique.
    `filters_json` is a JSON object mapping column -> allowed scalar/list values.
    """
    df = _load(file_path, sheet_name)
    missing = [
        c for c in (index_columns + value_columns + (column_columns or [])) if c not in df.columns
    ]
    if missing:
        raise KeyError(f"Kolonlar bulunamadı: {missing}")
    filters = json.loads(filters_json or "{}")
    if not isinstance(filters, dict):
        raise ValueError("filters_json JSON object olmalı")
    work = df.copy()
    for col, allowed in filters.items():
        if col not in work.columns:
            raise KeyError(f"Filtre kolonu bulunamadı: {col}")
        vals = allowed if isinstance(allowed, list) else [allowed]
        work = work[work[col].isin(vals)]
    aggfunc = aggfunc.lower()
    allowed_aggs = {"sum", "mean", "median", "count", "min", "max", "nunique"}
    if aggfunc not in allowed_aggs:
        raise ValueError(f"aggfunc şunlardan biri olmalı: {sorted(allowed_aggs)}")
    pivot = pd.pivot_table(
        work,
        index=index_columns,
        columns=column_columns or None,
        values=value_columns,
        aggfunc=aggfunc,
        fill_value=0,
        dropna=False,
    )
    if len(pivot) > 1_048_575 or len(pivot.reset_index().columns) > 16_384:
        raise ValueError(
            "Pivot Excel çalışma sayfası sınırlarını aşıyor; daha dar filtre/özet kullanın"
        )
    output = safe_output_path(output_name, ".xlsx")
    with safe_excel_writer(output) as writer:
        pivot.to_excel(writer, sheet_name="Pivot")
        work.head(50_000).to_excel(writer, sheet_name="Filtered Sample", index=False)
        wb = writer.book
        ws = writer.sheets["Pivot"]
        header_fmt = wb.add_format({"bold": True, "bg_color": "#E7E6E6", "border": 1})
        for col_num, _ in enumerate(pivot.reset_index().columns):
            ws.write(0, col_num, str(pivot.reset_index().columns[col_num]), header_fmt)
        ws.freeze_panes(1, max(1, len(index_columns)))
        ws.autofilter(0, 0, min(len(pivot), 100000), max(0, len(pivot.reset_index().columns) - 1))
    s = get_settings()
    audit(
        s.logs_dir,
        "pivot_analysis",
        file=file_path,
        output=str(output),
        rows=len(work),
        aggfunc=aggfunc,
    )
    return {
        "rows_after_filters": int(len(work)),
        "pivot_shape": [int(x) for x in pivot.shape],
        "aggfunc": aggfunc,
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "preview": pivot.reset_index().head(20).replace({np.nan: None}).to_dict(orient="records"),
    }


def create_excel_dashboard(
    file_path: str,
    output_name: str = "executive_dashboard.xlsx",
    category_column: str | None = None,
    value_column: str | None = None,
    date_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Create a generic executive Excel dashboard from a dataset.

    The function auto-detects useful numeric/categorical/date fields if the caller does not provide them.
    It creates raw-data, profile, KPI and chart sheets. The source file is never modified.
    """
    df = _load(file_path, sheet_name)
    roles = infer_column_roles(df)
    if value_column is None:
        if not roles["numeric"]:
            raise ValueError("Dashboard için en az bir numeric kolon gerekli")
        value_column = roles["numeric"][0]
    if value_column not in df.columns:
        raise KeyError(value_column)
    if category_column is None and roles["categorical"]:
        category_column = roles["categorical"][0]
    if date_column is None and roles["datetime"]:
        date_column = roles["datetime"][0]

    values = pd.to_numeric(df[value_column], errors="coerce")
    kpis = {
        "Row Count": int(len(df)),
        f"{value_column} Total": serializable(values.sum()),
        f"{value_column} Mean": serializable(values.mean()),
        f"{value_column} Median": serializable(values.median()),
        "Missing Cells": int(df.isna().sum().sum()),
        "Duplicate Rows": int(df.duplicated().sum()),
    }
    category = None
    if category_column and category_column in df.columns:
        tmp = pd.DataFrame({category_column: df[category_column], value_column: values}).dropna(
            subset=[category_column]
        )
        category = (
            tmp.groupby(category_column, dropna=False)[value_column]
            .agg(["sum", "mean", "count"])
            .sort_values("sum", ascending=False)
            .reset_index()
        )
    trend = None
    if date_column and date_column in df.columns:
        tmp = pd.DataFrame(
            {date_column: pd.to_datetime(df[date_column], errors="coerce"), value_column: values}
        ).dropna()
        if not tmp.empty:
            tmp["period"] = tmp[date_column].dt.to_period("M").astype(str)
            trend = tmp.groupby("period")[value_column].sum().reset_index()

    output = safe_output_path(output_name, ".xlsx")
    with safe_excel_writer(output) as writer:
        max_raw = min(len(df), 200_000)
        df.head(max_raw).to_excel(writer, sheet_name="Data", index=False)
        pd.DataFrame(list(kpis.items()), columns=["KPI", "Value"]).to_excel(
            writer, sheet_name="Dashboard", startrow=2, startcol=1, index=False
        )
        if category is not None:
            category.to_excel(writer, sheet_name="Category", index=False)
        if trend is not None:
            trend.to_excel(writer, sheet_name="Trend", index=False)

        wb = writer.book
        dash = writer.sheets["Dashboard"]
        title = wb.add_format({"bold": True, "font_size": 20})
        kpi_hdr = wb.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        num_fmt = wb.add_format({"num_format": "#,##0.00"})
        dash.write("B1", "Local Analytics Copilot — Executive Dashboard", title)
        dash.set_column("B:B", 34)
        dash.set_column("C:C", 18, num_fmt)
        dash.write("B3", "KPI", kpi_hdr)
        dash.write("C3", "Value", kpi_hdr)

        row_offset = 11
        if category is not None and len(category):
            chart = wb.add_chart({"type": "column"})
            n = min(len(category), 15)
            chart.add_series(
                {
                    "name": f"{value_column} by {category_column}",
                    "categories": f"=Category!$A$2:$A${n + 1}",
                    "values": f"=Category!$B$2:$B${n + 1}",
                }
            )
            chart.set_title({"name": f"Top {category_column} by {value_column}"})
            chart.set_legend({"none": True})
            dash.insert_chart(row_offset, 1, chart, {"x_scale": 1.5, "y_scale": 1.2})
            row_offset += 22
        if trend is not None and len(trend):
            chart2 = wb.add_chart({"type": "line"})
            n = len(trend)
            chart2.add_series(
                {
                    "name": f"Monthly {value_column}",
                    "categories": f"=Trend!$A$2:$A${n + 1}",
                    "values": f"=Trend!$B$2:$B${n + 1}",
                }
            )
            chart2.set_title({"name": f"Monthly Trend — {value_column}"})
            dash.insert_chart(row_offset, 1, chart2, {"x_scale": 1.5, "y_scale": 1.2})
        writer.sheets["Data"].freeze_panes(1, 0)

    s = get_settings()
    audit(s.logs_dir, "create_excel_dashboard", file=file_path, output=str(output))
    return {
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "value_column": value_column,
        "category_column": category_column,
        "date_column": date_column,
        "kpis": kpis,
        "raw_rows_exported": max_raw,
        "note": "Dashboard is a deterministic starter template; business KPI definitions should be approved before operational use.",
    }


def create_html_dashboard(
    file_path: str,
    output_name: str = "dashboard.html",
    value_column: str | None = None,
    category_column: str | None = None,
    date_column: str | None = None,
    sheet_name: str = "0",
) -> dict:
    """Create a self-contained interactive Plotly HTML dashboard."""
    import plotly.express as px
    import plotly.io as pio

    df = _load(file_path, sheet_name)
    roles = infer_column_roles(df)
    value_column = value_column or (roles["numeric"][0] if roles["numeric"] else None)
    category_column = category_column or (roles["categorical"][0] if roles["categorical"] else None)
    date_column = date_column or (roles["datetime"][0] if roles["datetime"] else None)
    if not value_column:
        raise ValueError("HTML dashboard için numeric kolon gerekli")

    figures = []
    vals = pd.to_numeric(df[value_column], errors="coerce")
    clean = vals.dropna()
    if len(clean):
        figures.append(
            px.histogram(
                pd.DataFrame({value_column: clean}),
                x=value_column,
                title=f"Distribution — {value_column}",
            )
        )
    if category_column:
        cat = pd.DataFrame({category_column: df[category_column], value_column: vals}).dropna(
            subset=[category_column]
        )
        agg = cat.groupby(category_column)[value_column].sum().nlargest(20).reset_index()
        figures.append(
            px.bar(agg, x=category_column, y=value_column, title=f"Top {category_column}")
        )
    if date_column:
        tr = pd.DataFrame(
            {date_column: pd.to_datetime(df[date_column], errors="coerce"), value_column: vals}
        ).dropna()
        if len(tr):
            tr["period"] = tr[date_column].dt.to_period("M").astype(str)
            trend = tr.groupby("period")[value_column].sum().reset_index()
            figures.append(
                px.line(trend, x="period", y=value_column, markers=True, title="Monthly Trend")
            )

    html_parts = [
        "<html><head><meta charset='utf-8'><title>Local Analytics Dashboard</title></head><body style='font-family:Arial;max-width:1200px;margin:auto'>",
        "<h1>Local Analytics Copilot Dashboard</h1>",
    ]
    for i, fig in enumerate(figures):
        html_parts.append(pio.to_html(fig, full_html=False, include_plotlyjs=i == 0))
    html_parts.append("</body></html>")
    output = safe_output_path(output_name, ".html")
    output.write_text("\n".join(html_parts), encoding="utf-8")
    s = get_settings()
    return {
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "charts": len(figures),
        "value_column": value_column,
        "category_column": category_column,
        "date_column": date_column,
    }
