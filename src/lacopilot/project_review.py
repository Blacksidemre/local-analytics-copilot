from __future__ import annotations

from pathlib import Path

from lacopilot.config import get_settings
from lacopilot.security import validate_local_model_name, validate_ollama_endpoint
from lacopilot.tools.common import safe_output_path


def run_local_project_review(model_mode: str = "deep") -> dict:
    """Ask a local Ollama model to review architecture/risk docs. No cloud service is used."""
    from ollama import Client

    s = get_settings()
    model = validate_local_model_name(s.choose_model(model_mode), allow_cloud=s.allow_cloud_models)
    host = validate_ollama_endpoint(s.ollama_host, allow_remote=s.allow_remote_ollama)
    docs = []
    for name in [
        "docs/MASTER_PLAN.md",
        "docs/ARCHITECTURE.md",
        "docs/RISK_REGISTER.md",
        "docs/MODEL_BENCHMARK.md",
        "pyproject.toml",
    ]:
        p = Path(name)
        if p.exists():
            docs.append(f"\n### {name}\n{p.read_text(encoding='utf-8', errors='ignore')[:30000]}")
    prompt = """You are a skeptical senior software architect, local-LLM agent engineer, statistician and security reviewer.
Review the Local Analytics Copilot project material below. Identify: correctness risks, data/privacy risks, statistical risks,
performance bottlenecks for a 16 GB VRAM / 32 GB RAM Windows workstation, missing tests, agent/tool-call failure modes,
and concrete revisions. Separate BLOCKER / HIGH / MEDIUM / LOW. Do not invent facts not present in the documents.
Then provide a go/no-go checklist for the next release.\n""" + "\n".join(docs)
    r = Client(host=host, timeout=s.ollama_timeout_seconds).chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"num_ctx": 32768, "num_predict": 5000},
    )
    out = safe_output_path("project_critic_review.md", ".md")
    out.write_text(r.message.content or "", encoding="utf-8")
    return {
        "model": model,
        "output": str(out.resolve().relative_to(s.workspace.resolve())),
        "characters": len(r.message.content or ""),
    }
