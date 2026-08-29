"""High-level, auditable tool surface exposed to the LLM.

The implementation contains many internal statistical functions, but the model only sees a
small number of tool families. This reduces tool-selection confusion and gives us one place
to enforce security/approval rules.
"""

from lacopilot.tools.action_tools import action_status
from lacopilot.tools.business_tools import business_engine
from lacopilot.tools.data_tools import (
    cleaning_plan,
    compare_schemas,
    generate_synthetic_dataset,
    inspect_dataset,
    list_workspace_files,
    profile_dataset,
    query_dataset_sql,
    validate_data_quality,
)
from lacopilot.tools.database_tools import database_catalog, database_describe, database_query
from lacopilot.tools.knowledge_tools import knowledge_ingest, knowledge_search
from lacopilot.tools.memory_tools import memory_list, memory_propose, workflow_suggestions
from lacopilot.tools.report_tools import create_pdf_summary
from lacopilot.tools.router_tools import analytics_engine, bi_engine, npl_engine
from lacopilot.tools.sql_tools import validate_sql_read_only
from lacopilot.tools.web_tools import public_web_search


def dataset_review(
    file_path: str, question: str = "", sheet_name: str = "0", create_dashboard: bool = False
) -> dict:
    """Run inspect + profiling + cleaning plan + analysis recommendation; optionally create an Excel dashboard."""
    from lacopilot.workflows import full_dataset_review

    return full_dataset_review(file_path, question, sheet_name, create_dashboard)


TOOLS = [
    list_workspace_files,
    inspect_dataset,
    profile_dataset,
    compare_schemas,
    validate_data_quality,
    cleaning_plan,
    generate_synthetic_dataset,
    query_dataset_sql,
    dataset_review,
    analytics_engine,
    bi_engine,
    npl_engine,
    business_engine,
    database_catalog,
    database_describe,
    database_query,
    knowledge_ingest,
    knowledge_search,
    memory_propose,
    memory_list,
    workflow_suggestions,
    public_web_search,
    create_pdf_summary,
    validate_sql_read_only,
    action_status,
]
TOOL_MAP = {fn.__name__: fn for fn in TOOLS}
