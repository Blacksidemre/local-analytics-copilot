from pathlib import Path

import pytest

from lacopilot.security import resolve_workspace_path, validate_read_only_sql


def test_workspace_path(tmp_path: Path):
    p = resolve_workspace_path(tmp_path, "incoming/a.csv")
    assert str(p).startswith(str(tmp_path.resolve()))
    with pytest.raises(PermissionError):
        resolve_workspace_path(tmp_path, "../secret.txt")


def test_sql_guard():
    assert validate_read_only_sql("SELECT * FROM x") == "SELECT * FROM x"
    with pytest.raises(PermissionError):
        validate_read_only_sql("DELETE FROM x")
    with pytest.raises(PermissionError):
        validate_read_only_sql("DROP TABLE x")
