# Cost & Model Policy

## Mandatory recurring cost
**None.** The default stack is local Ollama + open-weight models + Python libraries. No OpenAI/Anthropic/cloud API key is required.

The costs you still have are ordinary workstation costs: electricity, storage, and any software/company infrastructure you independently choose to license.

## Default model profile for RTX 5070 Ti 16 GB / 32 GB RAM
- **Fast/Main:** `qwen3.5:9b` — tool calling, thinking and multimodal support; about 6.6 GB model download in Ollama's current catalog.
- **Deep:** `gpt-oss:20b` — about 14 GB model download; intended for harder reasoning/review tasks. Context size strongly affects memory use.
- Keep the runtime context conservative (`32768`) first. Advertised maximum context is not the same thing as a practical 16 GB-VRAM setting.

Always run `lac benchmark-models` after installation. Actual tokens/sec, cold-load latency and tool reliability matter more than model marketing.

## Optional external cost
- Public web search is **off by default**.
- Hosted/cloud inference is not part of the default architecture.
- OpenClaw is optional orchestration; Local Analytics Copilot works without it.
