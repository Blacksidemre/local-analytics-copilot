from __future__ import annotations

import time

from lacopilot.config import get_settings


def benchmark_installed_models(model_names: list[str] | None = None) -> dict:
    """Small local benchmark: generation latency + one tool-call smoke test. No external API is used."""
    from ollama import Client

    s = get_settings()
    client = Client(host=s.ollama_host)
    installed = [m.model for m in client.list().models]
    candidates = model_names or installed
    rows = []
    tool = [
        {
            "type": "function",
            "function": {
                "name": "calculator_probe",
                "description": "Return supplied integer",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                },
            },
        }
    ]
    for model in candidates:
        if model not in installed:
            rows.append({"model": model, "installed": False})
            continue
        start = time.perf_counter()
        try:
            r = client.chat(
                model=model,
                messages=[
                    {"role": "user", "content": "Türkçe tek cümleyle veri kalitesini tanımla."}
                ],
                options={"num_predict": 80},
            )
            elapsed = time.perf_counter() - start
            t0 = time.perf_counter()
            tr = client.chat(
                model=model,
                messages=[
                    {"role": "user", "content": "calculator_probe aracını value=7 ile çağır."}
                ],
                tools=tool,
                options={"num_predict": 80},
            )
            t_elapsed = time.perf_counter() - t0
            calls = tr.message.tool_calls or []
            rows.append(
                {
                    "model": model,
                    "installed": True,
                    "generation_seconds": round(elapsed, 3),
                    "tool_seconds": round(t_elapsed, 3),
                    "tool_call_ok": bool(calls and calls[0].function.name == "calculator_probe"),
                    "sample": (r.message.content or "")[:200],
                }
            )
        except Exception as exc:
            rows.append({"model": model, "installed": True, "error": str(exc)})
    return {
        "results": rows,
        "note": "This is a smoke benchmark, not a full quality evaluation. Use the acceptance suite for model selection.",
    }
