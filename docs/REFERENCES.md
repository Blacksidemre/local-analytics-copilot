# External Design References

This project is original glue/application code, but its architecture was informed by established local-agent/data-analysis patterns.

## Ollama
- Model library: https://ollama.com/library
- Tool calling: https://docs.ollama.com/capabilities/tool-calling
- Qwen 3.5 catalog: https://ollama.com/library/qwen3.5
- GPT-OSS catalog: https://ollama.com/library/gpt-oss

## OpenClaw
- Repository/docs: https://github.com/openclaw/openclaw
- Ollama provider documentation in the OpenClaw docs/repository.
- Key design point used here: native Ollama API for local tool-calling; OpenClaw remains an optional orchestration layer.

## Microsoft Data Formulator
- https://github.com/microsoft/data-formulator
- Useful reference for conversational data transformation/visual analysis, local sandboxing and Ollama-configurable model endpoints.

## Open Interpreter
- https://github.com/openinterpreter/openinterpreter
- Useful reference for local computer/code agents. Local Analytics Copilot deliberately exposes narrower deterministic analytics tools instead of unrestricted shell execution by default.
