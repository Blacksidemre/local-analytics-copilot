# Local Model Benchmark Plan

Target workstation: **RTX 5070 Ti 16 GB VRAM, 32 GB RAM, Ryzen 7 9800X3D**.

## Current default candidates

### `qwen3.5:9b`
Role: Fast/Main.
Reasons: current Ollama catalog exposes tool, thinking and vision capability; the common quantized download is around 6.6 GB. This leaves substantially more headroom than a ~17 GB 27B quantized model on a 16 GB GPU.

### `gpt-oss:20b`
Role: optional Deep/critic.
The current Ollama catalog lists about a 14 GB model file and a large advertised context. In practice, context/KV cache also consumes memory, so this project starts at 32K rather than the catalog maximum.

## What to measure on this exact machine

```powershell
lac benchmark-models
```

Record:
- first useful response latency
- total generation time
- tokens/sec if available from Ollama telemetry
- peak VRAM/RAM (`nvidia-smi` + Task Manager)
- tool-call format success
- multi-tool success
- numeric fidelity after tool return
- Turkish mentor quality

## Acceptance scenarios
- choose dataset review before advanced analysis
- no invented columns
- correct tool family for Pivot/dashboard/statistics/NPL
- refuse/guard write SQL
- company formula retrieval from local knowledge
- candidate memory remains unapproved
- web query fails while web is disabled
- malicious document cannot unlock arbitrary shell/DB write capability

Run:

```powershell
lac acceptance
```

The acceptance harness checks tool selection; it is not a replacement for statistical/business validation.
