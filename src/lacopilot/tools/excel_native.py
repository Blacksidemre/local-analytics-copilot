from __future__ import annotations

import json

from lacopilot.config import get_settings
from lacopilot.security import resolve_workspace_path
from lacopilot.tools.common import load_table, safe_excel_writer, safe_output_path

_XL_AGG = {
    "sum": -4157,  # xlSum
    "count": -4112,  # xlCount
    "average": -4106,  # xlAverage
    "max": -4136,  # xlMax
    "min": -4139,  # xlMin
}


def create_native_excel_pivot(
    file_path: str,
    row_fields: list[str],
    data_fields_json: str,
    column_fields: list[str] | None = None,
    output_name: str = "native_pivot.xlsx",
    sheet_name: str = "0",
) -> dict:
    """Create a real Excel PivotTable via Windows Excel COM automation.

    Requires Windows, desktop Microsoft Excel and optional `pywin32` dependency.
    The source file is never modified; data is copied into a new workbook.

    `data_fields_json` example:
    [{"column":"total_balance","aggregation":"sum","caption":"Total Balance"}]
    """
    try:
        import win32com.client as win32
    except ImportError as exc:  # pragma: no cover - Windows optional
        raise RuntimeError(
            "Native Excel Pivot için Windows + Excel + `pip install pywin32` gerekli"
        ) from exc

    s = get_settings()
    source = resolve_workspace_path(s.workspace, file_path)
    fields = json.loads(data_fields_json)
    if not isinstance(fields, list) or not fields:
        raise ValueError("data_fields_json en az bir data field içeren JSON list olmalı")

    # Normalize any supported source to a temporary XLSX inside the sandbox.
    if source.suffix.lower() not in {".xlsx", ".xlsm"}:
        df = load_table(source, int(sheet_name) if str(sheet_name).isdigit() else sheet_name)
        temp = s.working_dir / (source.stem + "_pivot_source.xlsx")
        with safe_excel_writer(temp) as writer:
            df.head(1_048_575).to_excel(writer, index=False)
        source = temp

    output = safe_output_path(output_name, ".xlsx")

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    src_wb = out_wb = None
    try:
        src_wb = excel.Workbooks.Open(str(source.resolve()), ReadOnly=True)
        src_ws = src_wb.Worksheets.Item(
            int(sheet_name) + 1 if str(sheet_name).isdigit() else sheet_name
        )
        used = src_ws.UsedRange
        out_wb = excel.Workbooks.Add()
        data_ws = out_wb.Worksheets.Item(1)
        data_ws.Name = "Data"
        used.Copy(Destination=data_ws.Range("A1"))
        pivot_ws = out_wb.Worksheets.Add()
        pivot_ws.Name = "Pivot"
        last_row = data_ws.UsedRange.Rows.Count
        last_col = data_ws.UsedRange.Columns.Count
        source_data = f"'Data'!R1C1:R{last_row}C{last_col}"
        cache = out_wb.PivotCaches().Create(SourceType=1, SourceData=source_data)  # xlDatabase
        pt = cache.CreatePivotTable(TableDestination="'Pivot'!R3C1", TableName="LAC_Pivot")
        for pos, name in enumerate(row_fields, 1):
            f = pt.PivotFields(name)
            f.Orientation = 1
            f.Position = pos  # xlRowField
        for pos, name in enumerate(column_fields or [], 1):
            f = pt.PivotFields(name)
            f.Orientation = 2
            f.Position = pos  # xlColumnField
        for spec in fields:
            col = spec["column"]
            agg = str(spec.get("aggregation", "sum")).lower()
            if agg not in _XL_AGG:
                raise ValueError(f"Aggregation desteklenmiyor: {agg}")
            caption = spec.get("caption") or f"{agg.title()} of {col}"
            pt.AddDataField(pt.PivotFields(col), caption, _XL_AGG[agg])
        pivot_ws.Columns.AutoFit()
        data_ws.Columns.AutoFit()
        out_wb.SaveAs(str(output.resolve()), FileFormat=51)  # xlsx
    finally:
        if src_wb is not None:
            src_wb.Close(False)
        if out_wb is not None:
            out_wb.Close(True)
        excel.Quit()
    return {
        "output": str(output.resolve().relative_to(s.workspace.resolve())),
        "native_excel_pivot": True,
        "row_fields": row_fields,
        "column_fields": column_fields or [],
        "data_fields": fields,
    }
