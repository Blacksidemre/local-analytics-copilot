from __future__ import annotations

from pathlib import Path

import yaml

from lacopilot.llm import OllamaAgent


def run_acceptance(
    path: str = "evals/acceptance_tasks.yaml",
    personality: str = "technical",
    model_mode: str = "main",
) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    rows = []
    for task in data.get("tasks", []):
        try:
            r = OllamaAgent(personality=personality, model_mode=model_mode).chat(task["prompt"])
            used = [e["tool"] for e in r.get("tool_events", [])]
            expected = task.get("expected_tools", [])
            ok = all(x in used for x in expected)
            rows.append(
                {
                    "id": task["id"],
                    "ok": ok,
                    "expected": expected,
                    "used": used,
                    "answer_preview": r.get("answer", "")[:300],
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "id": task["id"],
                    "ok": False,
                    "error": str(exc),
                    "expected": task.get("expected_tools", []),
                }
            )
    return {
        "passed": sum(bool(r["ok"]) for r in rows),
        "total": len(rows),
        "results": rows,
        "note": "Tool-selection acceptance is only one layer; inspect statistical correctness and business definitions separately.",
    }
