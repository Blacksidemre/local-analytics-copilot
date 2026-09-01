# Canonical Product Architecture

Status: **single-repository pre-release**

```text
Tauri / Next UI
      ↓ same-origin local proxy
FastAPI Data Bridge
      ├─ Quick: deterministic profile → dashboard → optional verified explanation
      ├─ Analyst: explicit target → statistics → findings → verifier → reports
      └─ Agent: Ollama planner → bounded typed tools → evidence → verifier → synthesis
```

## Trust boundary

The LLM is never the authoritative calculation engine. It may create a bounded typed plan and
explain supplied evidence. Python/DuckDB/SciPy/statsmodels tools calculate; stable `finding_id` and
source fields bind each numeric fact; independent validators decide what the UI and reports may
show.

The Agent has no arbitrary Python, shell, PowerShell, SQL, filesystem, internet or raw-row-dump
tool. Tool/failure budgets, duplicate-call protection, dependency validation and loop detection
terminate unsafe or unproductive plans. Unsupported numbers and business/KPI/causality semantics
fail closed.

## Data and evidence flow

1. CSV/XLSX is copied into the local workspace and parsed deterministically.
2. Schema, roles, quality metrics and bounded aggregates are produced before model use.
3. Quick/Analyst/Agent findings carry stable IDs and deterministic sources.
4. Verifier-passed Agent manifests may be stored locally without raw rows or internal model prompts.
5. Two archived manifests may be compared mechanically; period/business meaning is not inferred.
6. Excel/HTML/PDF reports are generated from one verified manifest and reopened for validation.

## Desktop lifecycle

The canonical launcher manages the analytics backend and Next UI. The packaged Tauri shell uses
loopback-only ephemeral ports, a per-launch local API token, relative packaged resource paths and
owned-child cleanup. The packaged backend is a PyInstaller resource; the UI server is a bundled Node
sidecar. Ollama is local and optional for deterministic Quick/Analyst operation.

## Local storage

- Workspace, outputs, logs, config and history are local and Git-ignored.
- History is deletable and project/dataset fingerprinted.
- Archived evidence is never promoted into a current analysis automatically.
- Company definitions require explicit approved metadata; a column name is not a KPI definition.

Detailed Agent design: [`ADR-001-agent-core.md`](ADR-001-agent-core.md). Privacy controls:
[`PRIVACY_AND_SECURITY.md`](PRIVACY_AND_SECURITY.md). Release gates:
[`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md).
