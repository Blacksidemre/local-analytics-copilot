from __future__ import annotations

import pandas as pd

from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table, safe_excel_writer, safe_output_path


def create_excel_profile_report(
    file_path: str, output_name: str = "analytics_report.xlsx", sheet_name: str = "0"
) -> dict:
    """Create a professional starter Excel report with raw data, data quality and descriptive statistics.

    Args:
        file_path: Workspace-relative CSV/XLSX/Parquet path.
        output_name: File name written inside workspace/outputs. Must end with .xlsx.
        sheet_name: Excel sheet or numeric index as text.
    """
    s = get_settings()
    path = resolve_workspace_path(s.workspace, file_path)
    sheet = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
    df = load_table(path, sheet)
    output = safe_output_path(output_name, ".xlsx")
    numeric = df.select_dtypes(include="number")
    desc = (
        numeric.describe().T.reset_index().rename(columns={"index": "column"})
        if len(numeric.columns)
        else pd.DataFrame({"message": ["No numeric columns"]})
    )
    dq = pd.DataFrame(
        {
            "column": df.columns.astype(str),
            "dtype": [str(x) for x in df.dtypes],
            "missing_count": [int(df[c].isna().sum()) for c in df.columns],
            "missing_pct": [round(float(df[c].isna().mean() * 100), 2) for c in df.columns],
            "unique_count": [int(df[c].nunique(dropna=True)) for c in df.columns],
        }
    )
    max_raw = min(len(df), 1_048_575)
    with safe_excel_writer(output) as writer:
        df.head(max_raw).to_excel(writer, sheet_name="Data", index=False)
        dq.to_excel(writer, sheet_name="Data Quality", index=False)
        desc.to_excel(writer, sheet_name="Descriptive", index=False)
        wb = writer.book
        header = wb.add_format(
            {"bold": True, "bg_color": "#1F4E78", "font_color": "white", "border": 1}
        )
        for ws_name in ["Data", "Data Quality", "Descriptive"]:
            ws = writer.sheets[ws_name]
            ws.freeze_panes(1, 0)
            ws.autofilter(
                0,
                0,
                max(
                    0,
                    (df if ws_name == "Data" else dq if ws_name == "Data Quality" else desc).shape[
                        0
                    ],
                ),
                max(
                    0,
                    (df if ws_name == "Data" else dq if ws_name == "Data Quality" else desc).shape[
                        1
                    ]
                    - 1,
                ),
            )
            ws.set_row(0, None, header)
            ws.set_column(0, 30, 16)
        summary = wb.add_worksheet("Executive Summary")
        summary.write("A1", "LOCAL ANALYTICS COPILOT - DATASET SUMMARY", header)
        summary.write("A3", "Rows")
        summary.write("B3", len(df))
        summary.write("A4", "Columns")
        summary.write("B4", df.shape[1])
        summary.write("A5", "Duplicate rows")
        summary.write("B5", int(df.duplicated().sum()))
        summary.write("A6", "Missing cells")
        summary.write("B6", int(df.isna().sum().sum()))
        summary.set_column("A:A", 28)
        summary.set_column("B:B", 18)
    return {
        "status": "success",
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "raw_rows_exported": int(max_raw),
        "raw_data_truncated": bool(len(df) > max_raw),
    }
