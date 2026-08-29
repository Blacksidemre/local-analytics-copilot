from __future__ import annotations

from lacopilot.workflows import full_dataset_review


def dataset_review(
    file_path: str, question: str = "", sheet_name: str = "0", create_dashboard: bool = False
) -> dict:
    """Run inspect + profiling + data-quality/cleaning plan + analysis recommendation; optionally create an Excel dashboard."""
    return full_dataset_review(file_path, question, sheet_name, create_dashboard)
