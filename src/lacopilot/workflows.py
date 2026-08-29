from __future__ import annotations

from lacopilot.tools.bi_tools import create_excel_dashboard
from lacopilot.tools.data_tools import cleaning_plan, inspect_dataset, profile_dataset
from lacopilot.tools.statistics_tools import recommend_analysis


def full_dataset_review(
    file_path: str, question: str = "", sheet_name: str = "0", create_dashboard: bool = False
) -> dict:
    """Deterministic first-pass workflow for a new dataset."""
    result = {
        "inspect": inspect_dataset(file_path, sheet_name, 5),
        "profile": profile_dataset(file_path, sheet_name),
        "analysis_plan": recommend_analysis(file_path, question, sheet_name),
        "cleaning_plan": cleaning_plan(file_path, sheet_name),
    }
    if create_dashboard:
        try:
            result["dashboard"] = create_excel_dashboard(file_path, sheet_name=sheet_name)
        except Exception as exc:
            result["dashboard"] = {"skipped": True, "reason": str(exc)}
    return result
