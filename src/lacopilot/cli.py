from __future__ import annotations

import ipaddress
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lacopilot.actions import ActionStore
from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.hardware import detect_hardware
from lacopilot.knowledge import KnowledgeBase
from lacopilot.llm import OllamaAgent
from lacopilot.memory import LocalMemory
from lacopilot.model_benchmark import benchmark_installed_models
from lacopilot.personality import load_profiles
from lacopilot.security import validate_local_model_name, validate_ollama_endpoint
from lacopilot.tools import TOOL_MAP
from lacopilot.tools.data_tools import profile_dataset
from lacopilot.workflows import full_dataset_review

app = typer.Typer(help="Local Analytics Copilot CLI")
console = Console()


@app.command()
def doctor():
    """Check hardware, workspace and Ollama reachability."""
    s = get_settings()
    hw = detect_hardware()
    console.print(Panel(json.dumps(hw, ensure_ascii=False, indent=2), title="Hardware"))
    console.print(f"Workspace: {s.workspace.resolve()}")
    console.print(f"Model modes: fast={s.fast_model} | main={s.model} | deep={s.deep_model}")
    try:
        import urllib.request

        host = validate_ollama_endpoint(s.ollama_host, allow_remote=s.allow_remote_ollama)
        for model in (s.fast_model, s.model, s.deep_model):
            validate_local_model_name(model, allow_cloud=s.allow_cloud_models)
        with urllib.request.urlopen(host + "/api/tags", timeout=3) as r:
            data = json.load(r)
        models = [m.get("name") or m.get("model") for m in data.get("models", [])]
        console.print(f"[green]Ollama OK[/green] — {len(models)} local model")
        console.print("Installed: " + (", ".join(models) if models else "none"))
    except Exception as exc:
        console.print(f"[yellow]Ollama erişilemiyor:[/yellow] {exc}")
        console.print("Ollama'yı kurup `ollama serve` ve ardından model pull işlemini yapın.")


@app.command()
def analyze(file_path: str, sheet_name: str = "0"):
    """Run deterministic profiling without an LLM."""
    console.print_json(data=profile_dataset(file_path, sheet_name))


@app.command("review")
def review_dataset(
    file_path: str, question: str = "", sheet_name: str = "0", dashboard: bool = False
):
    """Run the full deterministic first-pass workflow."""
    console.print_json(data=full_dataset_review(file_path, question, sheet_name, dashboard))


@app.command()
def chat(message: str, personality: str = "mentor", mode: str = "main"):
    """Ask the local Ollama tool-calling agent."""
    result = OllamaAgent(personality=personality, model_mode=mode).chat(message)
    console.print(result["answer"])
    if result["tool_events"]:
        console.print(
            Panel(
                json.dumps(result["tool_events"], ensure_ascii=False, indent=2), title="Tool trace"
            )
        )


@app.command()
def personalities():
    """List editable personality profiles."""
    t = Table("Key", "Label", "Teaching", "Technical")
    for key, p in load_profiles().items():
        t.add_row(
            key, str(p.get("label")), str(p.get("teaching_level")), str(p.get("technical_depth"))
        )
    console.print(t)


@app.command("memory-list")
def memory_list(status: str = "candidate"):
    """List local memory entries."""
    console.print_json(data=LocalMemory(get_settings().memory_db).list(status=status or None))


@app.command("memory-approve")
def memory_approve(memory_id: int):
    """Human approval gate for a candidate rule/memory."""
    LocalMemory(get_settings().memory_db).approve(memory_id)
    console.print(f"[green]Approved[/green] memory #{memory_id}")


@app.command("memory-reject")
def memory_reject(memory_id: int):
    LocalMemory(get_settings().memory_db).reject(memory_id)
    console.print(f"[yellow]Rejected[/yellow] memory #{memory_id}")


@app.command("knowledge-ingest")
def knowledge_ingest(file_path: str, embed_model: str = "", ocr: bool = False):
    console.print_json(
        data=KnowledgeBase().ingest(file_path, embed_model=embed_model or None, ocr=ocr)
    )


@app.command("knowledge-ingest-folder")
def knowledge_ingest_folder(folder: str = "knowledge", embed_model: str = "", ocr: bool = False):
    console.print_json(
        data=KnowledgeBase().ingest_folder(folder, embed_model=embed_model or None, ocr=ocr)
    )


@app.command("knowledge-search")
def knowledge_search(query: str, top_k: int = 5, embed_model: str = ""):
    console.print_json(
        data=KnowledgeBase().search(query, top_k=top_k, embed_model=embed_model or None)
    )


@app.command("benchmark-models")
def benchmark_models(models: str = ""):
    """Run a small local generation/tool-calling benchmark against installed Ollama models."""
    names = [x.strip() for x in models.split(",") if x.strip()] or None
    console.print_json(data=benchmark_installed_models(names))


@app.command()
def watch():
    """Watch workspace/incoming and auto-profile new datasets."""
    from lacopilot.watcher import watch_incoming

    console.print("Watching workspace/incoming. Ctrl+C to stop.")
    watch_incoming()


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8765):
    """Start the local browser UI and API."""
    import uvicorn

    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    s = get_settings()
    if not loopback and not s.allow_network_bind:
        raise typer.BadParameter(
            "Ağ arayüzüne bağlanma varsayılan olarak kapalı. Bilinçli kullanım için "
            "LAC_ALLOW_NETWORK_BIND=true ve LAC_API_TOKEN ayarlayın."
        )
    if not loopback and not s.api_token:
        raise typer.BadParameter("Ağ erişimi için boş olmayan LAC_API_TOKEN zorunludur.")
    uvicorn.run("lacopilot.app:app", host=host, port=port, reload=False)


def _execute_action(tool_name: str, arguments: dict):
    fn = TOOL_MAP.get(tool_name)
    if not fn or tool_name == "action_status":
        raise PermissionError(f"Onaylanan action için araç bulunamadı: {tool_name}")
    audit(get_settings().logs_dir, "action_execute", tool=tool_name, args=arguments)
    return fn(**arguments)


@app.command("action-list")
def action_list(status: str = "pending"):
    """List queued workspace-write or external actions."""
    console.print_json(data=ActionStore(get_settings().actions_db).list(status=status or None))


@app.command("action-approve")
def action_approve(action_id: str):
    """Approve and execute the exact queued tool call."""
    result = ActionStore(get_settings().actions_db).approve_and_execute(
        action_id,
        _execute_action,
    )
    console.print_json(data=result)


@app.command("action-reject")
def action_reject(action_id: str):
    """Reject a queued tool call without executing it."""
    console.print_json(data=ActionStore(get_settings().actions_db).reject(action_id))


@app.command("learning-profile")
def learning_profile():
    """Show the local mentor learning profile."""
    console.print_json(data=LocalMemory(get_settings().memory_db).learning_profile())


@app.command("learning-update")
def learning_update(topic: str, delta: float, note: str = ""):
    """Explicitly record learning progress; delta is clamped to +/-25."""
    d = max(-25.0, min(25.0, float(delta)))
    console.print_json(data=LocalMemory(get_settings().memory_db).update_learning(topic, d, note))


@app.command("privacy-check")
def privacy_check():
    """Show local-first/privacy configuration status."""
    from lacopilot.privacy import privacy_status

    console.print_json(data=privacy_status())


@app.command("project-review")
def project_review(mode: str = "deep"):
    """Run a local critic model over architecture/risk docs."""
    from lacopilot.project_review import run_local_project_review

    console.print_json(data=run_local_project_review(mode))


@app.command("acceptance")
def acceptance(mode: str = "main"):
    """Run local agent tool-selection acceptance prompts."""
    from lacopilot.evals import run_acceptance

    console.print_json(data=run_acceptance(model_mode=mode))


if __name__ == "__main__":
    app()
