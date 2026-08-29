# OpenClaw Integration

OpenClaw is an **optional orchestration layer**, not a dependency of the deterministic analytics engine.

**RC1 status:** experimental and not part of the automated release gate. OpenClaw's official Ollama
provider documentation recommends the native Ollama API. Provider behavior has also changed across
releases, so validate the exact OpenClaw version and every approved tool path on the target machine.

Why:
1. Statistics/Excel/NPL functions should remain testable if the agent framework changes.
2. OpenClaw is useful for scheduling, skills, nodes, plugins and multi-step orchestration.
3. Local Ollama should use the **native Ollama API** (`http://127.0.0.1:11434`) for tool calling; do not append `/v1` in this mode.

Files in `openclaw/`:
- `SKILL.md` — operating rules
- `ollama-provider.example.json5` — example local provider config

Official provider reference: https://docs.openclaw.ai/providers/ollama

Suggested architecture:

```text
OpenClaw (optional)
        |
        +--> Ollama local model
        |
        +--> Local Analytics Copilot FastAPI/OpenAPI
                  |
                  +--> deterministic Statistics/BI/NPL/SQL/RAG tools
```

Do not grant OpenClaw unrestricted shell/filesystem/database permissions just because the local LLM is trusted. Keep the allowlist narrow.

## Optional API token
If `LAC_API_TOKEN` is set, calls to `/api/*` must include either `X-LAC-Token: <token>` or `Authorization: Bearer <token>`. Configure the same header in the local OpenClaw/OpenAPI bridge. Keep the token in environment/secret configuration, not in prompts.
