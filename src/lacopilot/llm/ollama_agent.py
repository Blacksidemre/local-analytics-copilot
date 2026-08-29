from __future__ import annotations

import json
from typing import Any

from lacopilot.actions import ActionStore
from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.memory import LocalMemory
from lacopilot.personality import load_profile, system_prompt
from lacopilot.security import validate_local_model_name, validate_ollama_endpoint
from lacopilot.tool_policy import approval_required
from lacopilot.tools import TOOL_MAP, TOOLS


class OllamaAgent:
    def __init__(
        self,
        model: str | None = None,
        personality: str | None = None,
        model_mode: str | None = None,
    ):
        self.settings = get_settings()
        self.model = validate_local_model_name(
            model or self.settings.choose_model(model_mode),
            allow_cloud=self.settings.allow_cloud_models,
        )
        self.ollama_host = validate_ollama_endpoint(
            self.settings.ollama_host,
            allow_remote=self.settings.allow_remote_ollama,
        )
        self.personality = personality or self.settings.personality

    def chat(self, user_message: str, history: list[dict[str, Any]] | None = None) -> dict:
        try:
            from ollama import Client
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ollama Python paketi kurulu değil. `pip install -e .` çalıştırın."
            ) from exc

        if len(user_message) > self.settings.max_chat_chars:
            raise ValueError(
                f"Mesaj {self.settings.max_chat_chars} karakter sınırını aşıyor; ham veri satırlarını sohbete yapıştırmayın."
            )
        profile = load_profile(self.personality)
        memory_store = LocalMemory(self.settings.memory_db)
        approved_memory = memory_store.approved_context(limit=40)
        learning_rows = memory_store.learning_profile()
        learning_context = "\n".join(
            f"{r['topic']}: {float(r['score']):.0f}/100 ({r['evidence_count']} evidence)"
            for r in learning_rows[:30]
        )
        client = Client(host=self.ollama_host, timeout=self.settings.ollama_timeout_seconds)
        messages = [
            {
                "role": "system",
                "content": system_prompt(
                    profile, approved_memory=approved_memory, learning_context=learning_context
                ),
            }
        ]
        if history:
            # Keep a bounded, explicit chat history. Tool results are not persisted here.
            bounded: list[dict[str, Any]] = []
            used = 0
            for item in reversed(history[-24:]):
                role = str(item.get("role", "user"))
                if role not in {"user", "assistant"}:
                    continue
                content = str(item.get("content", ""))
                if used + len(content) > self.settings.max_history_chars:
                    break
                bounded.append({"role": role, "content": content})
                used += len(content)
            messages.extend(reversed(bounded))
        messages.append({"role": "user", "content": user_message})
        tool_events = []

        options = {
            "num_ctx": int(self.settings.context_window),
            "num_predict": int(self.settings.max_output_tokens),
        }

        for round_no in range(1, self.settings.max_tool_rounds + 1):
            try:
                response = client.chat(
                    model=self.model, messages=messages, tools=TOOLS, think=True, options=options
                )
            except Exception as exc:
                msg = str(exc).lower()
                # Some local models do not expose a thinking toggle. Retry once without it.
                if round_no == 1 and "think" in msg:
                    response = client.chat(
                        model=self.model, messages=messages, tools=TOOLS, options=options
                    )
                elif (
                    round_no == 1
                    and ("not found" in msg or "pull" in msg)
                    and self.model != self.settings.model
                ):
                    # Deep model is optional. Fall back to the configured main model if it is not installed.
                    self.model = validate_local_model_name(
                        self.settings.model,
                        allow_cloud=self.settings.allow_cloud_models,
                    )
                    response = client.chat(
                        model=self.model,
                        messages=messages,
                        tools=TOOLS,
                        think=True,
                        options=options,
                    )
                else:
                    raise
            messages.append(response.message)
            calls = response.message.tool_calls or []
            if not calls:
                content = response.message.content or ""
                audit(
                    self.settings.logs_dir,
                    "agent_complete",
                    model=self.model,
                    rounds=round_no,
                    tools=len(tool_events),
                )
                if tool_events:
                    LocalMemory(self.settings.memory_db).add_experience(
                        task_type="agent_session",
                        summary=user_message[:240],
                        outcome="completed",
                        reusable=True,
                        metadata={"tools": [e["tool"] for e in tool_events], "model": self.model},
                    )
                return {
                    "answer": content,
                    "tool_events": tool_events,
                    "model": self.model,
                    "personality": self.personality,
                }

            for call in calls:
                name = call.function.name
                args = dict(call.function.arguments or {})
                fn = TOOL_MAP.get(name)
                if not fn:
                    result: Any = {"error": f"Unknown tool: {name}"}
                else:
                    risk = approval_required(name, args, self.settings)
                    if risk:
                        action = ActionStore(self.settings.actions_db).enqueue(
                            name,
                            args,
                            risk.kind,
                            risk.reason,
                        )
                        result = {
                            "status": "approval_required",
                            "action_id": action["id"],
                            "tool": name,
                            "arguments": args,
                            "risk_kind": risk.kind,
                            "reason": risk.reason,
                            "instruction": "Bu işlem çalıştırılmadı. Kullanıcı exact action'ı UI/API/CLI üzerinden onaylamalı.",
                        }
                    else:
                        try:
                            result = fn(**args)
                        except Exception as exc:
                            result = {"error": type(exc).__name__, "message": str(exc)}
                serialized = json.dumps(result, ensure_ascii=False, default=str)
                truncated = len(serialized) > self.settings.max_tool_result_chars
                tool_payload = serialized[: self.settings.max_tool_result_chars]
                if truncated:
                    tool_payload += "\n...[tool result truncated for context safety]"
                tool_events.append(
                    {
                        "tool": name,
                        "arguments": args,
                        "ok": not (
                            isinstance(result, dict)
                            and ("error" in result or result.get("status") == "approval_required")
                        ),
                        "status": result.get("status") if isinstance(result, dict) else None,
                        "result_preview": serialized[:1400],
                        "truncated_for_model": truncated,
                    }
                )
                audit(
                    self.settings.logs_dir,
                    "tool_call",
                    tool=name,
                    args=args,
                    ok=not (
                        isinstance(result, dict)
                        and ("error" in result or result.get("status") == "approval_required")
                    ),
                    status=result.get("status") if isinstance(result, dict) else None,
                )
                messages.append({"role": "tool", "tool_name": name, "content": tool_payload})

        raise RuntimeError(f"Agent {self.settings.max_tool_rounds} tool turu sınırına ulaştı")
