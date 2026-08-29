import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lacopilot.actions import ActionStore
from lacopilot.app import app
from lacopilot.config import get_settings
from lacopilot.llm import OllamaAgent


def configure(tmp_path: Path, monkeypatch, token: str = ""):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LAC_CONFIG_DIR", str(tmp_path / "config"))
    if token:
        monkeypatch.setenv("LAC_API_TOKEN", token)
    else:
        monkeypatch.delenv("LAC_API_TOKEN", raising=False)
    get_settings.cache_clear()
    return get_settings()


def test_action_store_deduplicates_and_executes_exact_arguments(tmp_path):
    store = ActionStore(tmp_path / "actions.sqlite3")
    first = store.enqueue("write_report", {"name": "a"}, "workspace_write", "test")
    duplicate = store.enqueue("write_report", {"name": "a"}, "workspace_write", "test")
    assert first["id"] == duplicate["id"]
    captured = {}

    def execute(name, arguments):
        captured.update({"name": name, "arguments": arguments})
        return {"ok": True}

    completed = store.approve_and_execute(first["id"], execute)
    assert completed["status"] == "completed"
    assert captured == {"name": "write_report", "arguments": {"name": "a"}}


def test_api_token_action_approval_and_security_headers(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch, token="correct-token")
    store = ActionStore(settings.actions_db)
    action = store.enqueue(
        "create_pdf_summary",
        {
            "title": "Audit",
            "sections_json": '[{"heading":"Result","body":"Safe"}]',
            "output_name": "approved.pdf",
        },
        "workspace_write",
        "Creates a report",
    )
    client = TestClient(app)
    assert client.get("/api/privacy").status_code == 401
    response = client.get("/api/privacy", headers={"X-LAC-Token": "correct-token"})
    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    approved = client.post(
        f"/api/actions/{action['id']}/approve",
        headers={"Authorization": "Bearer correct-token"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"
    assert (settings.outputs_dir / "approved.pdf").exists()
    assert (
        client.post(
            f"/api/actions/{action['id']}/approve",
            headers={"X-LAC-Token": "correct-token"},
        ).status_code
        == 409
    )
    assert client.get("/health").json() == {"status": "ok", "version": "1.0.0rc1"}


def test_agent_queues_write_tool_without_executing(tmp_path, monkeypatch):
    settings = configure(tmp_path, monkeypatch)

    class FakeClient:
        calls = 0

        def __init__(self, **_kwargs):
            pass

        def chat(self, **_kwargs):
            type(self).calls += 1
            if type(self).calls == 1:
                function = SimpleNamespace(
                    name="create_pdf_summary",
                    arguments={
                        "title": "Queued",
                        "sections_json": '[{"heading":"A","body":"B"}]',
                        "output_name": "must_not_exist.pdf",
                    },
                )
                message = SimpleNamespace(
                    content="", tool_calls=[SimpleNamespace(function=function)]
                )
            else:
                message = SimpleNamespace(content="Onayınızı bekliyorum.", tool_calls=[])
            return SimpleNamespace(message=message)

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=FakeClient))
    result = OllamaAgent().chat("Bir PDF oluştur")
    assert result["tool_events"][0]["status"] == "approval_required"
    assert not (settings.outputs_dir / "must_not_exist.pdf").exists()
    pending = ActionStore(settings.actions_db).list("pending")
    assert len(pending) == 1
    assert pending[0]["tool_name"] == "create_pdf_summary"
