from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.security import (
    validate_dataset_sql,
    validate_external_url,
    validate_local_model_name,
    validate_ollama_endpoint,
    validate_public_web_query,
    validate_read_only_sql,
)
from lacopilot.tool_policy import approval_required, classify_tool_call
from lacopilot.tools.data_tools import query_dataset_sql
from lacopilot.tools.excel_tools import create_excel_profile_report


def configure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LAC_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    return get_settings()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM accounts",
        "SELECT 1; DROP TABLE accounts",
        "WITH deleted AS (DELETE FROM accounts RETURNING *) SELECT * FROM deleted",
        "CREATE TABLE copied AS SELECT * FROM accounts",
        "SELECT * INTO temp_table FROM accounts",
        "COPY accounts TO '/tmp/accounts.csv'",
    ],
)
def test_read_only_sql_blocks_mutation(sql):
    with pytest.raises(PermissionError):
        validate_read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_csv_auto('/etc/passwd')",
        "SELECT * FROM glob('/tmp/*')",
        "SELECT * FROM secret_table",
        "CALL pragma_version()",
    ],
)
def test_dataset_sql_blocks_external_access(sql):
    with pytest.raises(PermissionError):
        validate_dataset_sql(sql)


def test_dataset_sql_executes_only_registered_dataframe(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    pd.DataFrame({"portfolio": ["A", "A", "B"], "balance": [10, 15, 8]}).to_csv(
        settings.incoming_dir / "portfolio.csv", index=False
    )
    result = query_dataset_sql(
        "incoming/portfolio.csv",
        "SELECT portfolio, SUM(balance) AS total FROM data GROUP BY portfolio ORDER BY portfolio",
    )
    assert result["rows"] == [
        {"portfolio": "A", "total": 25.0},
        {"portfolio": "B", "total": 8.0},
    ]
    with pytest.raises(PermissionError):
        query_dataset_sql("incoming/portfolio.csv", "SELECT * FROM read_csv_auto('/etc/passwd')")


def test_local_model_and_network_guards():
    assert validate_ollama_endpoint("http://127.0.0.1:11434")
    assert validate_ollama_endpoint("http://192.168.1.10:11434")
    with pytest.raises(PermissionError):
        validate_ollama_endpoint("https://models.example.com")
    with pytest.raises(PermissionError):
        validate_local_model_name("qwen3.5:cloud")
    with pytest.raises(PermissionError):
        validate_external_url("http://127.0.0.1/private")


def test_web_query_blocks_pii_and_secrets():
    assert validate_public_web_query("BDDK NPL mevzuatı")
    with pytest.raises(PermissionError):
        validate_public_web_query("müşteri 12345678901 hakkında araştır")
    with pytest.raises(PermissionError):
        validate_public_web_query("api_key=super-secret-value")


def test_excel_output_treats_formula_like_input_as_text(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    pd.DataFrame({"name": ["=2+2", "https://example.com"], "amount": [1, 2]}).to_csv(
        settings.incoming_dir / "formula.csv", index=False
    )
    result = create_excel_profile_report("incoming/formula.csv", output_name="safe.xlsx")
    workbook = load_workbook(settings.workspace / result["output"], data_only=False)
    assert workbook["Data"]["A2"].value == "=2+2"
    assert workbook["Data"]["A2"].data_type == "s"
    assert workbook["Data"]["A3"].hyperlink is None


def test_audit_redacts_sensitive_values(tmp_path):
    audit(
        tmp_path,
        "test",
        api_token="top-secret",
        text="mail user@example.com and identity 12345678901",
    )
    content = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "top-secret" not in content
    assert "user@example.com" not in content
    assert "12345678901" not in content


def test_tool_policy_requires_expected_approvals(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)
    assert classify_tool_call("profile_dataset", {}).kind == "read"
    assert classify_tool_call("public_web_search", {}).kind == "external"
    assert (
        classify_tool_call("analytics_engine", {"action": "anomaly", "params_json": "{}"}).kind
        == "workspace_write"
    )
    assert approval_required("bi_engine", {}, settings).kind == "workspace_write"
