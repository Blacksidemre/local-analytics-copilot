# Hermetic Hybrid Architecture

Status: canonical single-repository architecture on `hermetic-hybrid-integration`
Decision date: 2026-08-29

## Product boundary

The product is one canonical repository and one launcher, with two cooperating local processes
inside the desktop boundary:

```text
Hermetic-derived Next/Tauri UI
        |
        | localhost-only versioned HTTP contract
        v
LAC Deterministic Data Bridge + Analytics API
        |
        +-- pandas / DuckDB / SciPy / statsmodels / sklearn
        +-- NPL and business engines
        +-- audit / approval / policy / memory / reporting
        +-- local Ollama interpretation
```

The Hermetic-derived source now lives in `apps/desktop` with its original licenses and notices.
It owns product interaction and visualization. LAC owns ingestion truth, calculations,
business rules, and claim evidence. The language model may plan and explain; it is not the source
of row counts, missing counts, duplicate counts, KPIs, statistical results, or benchmarks.

## Inspected baselines

| Codebase | Inspected revision | Important observation |
|---|---:|---|
| Local Analytics Copilot | `cfbc2e2` | Strong deterministic analytics/security core; basic UI and generic agent surface |
| Hermetic upstream | `04e4dca` | Tauri desktop shell, artifacts/findings/dashboard and XLSX sheet picker exist |

The current Hermetic upstream is newer than the Windows ZIP previously tested. Its XLSX and Tauri
work should be borrowed. Its CSV parser still tolerates some field-count mismatches, and its provider
capability gate still disables Investigate for Ollama/MLX/llama.cpp. Those two areas remain explicit
replacement/build work.

## Build / Borrow / Keep / Replace matrix

| Capability | Decision | Owner for the hybrid |
|---|---|---|
| Product UI, history UX, artifact viewer | BORROW | `apps/desktop` in canonical LAC repo |
| Charts, dashboard composer, findings presentation | BORROW + HARDEN | `apps/desktop` |
| Tauri desktop packaging and sidecar pattern | BORROW | `apps/desktop/src-tauri` |
| Docker sandbox UX/runtime | BORROW | `apps/desktop/docker` |
| CSV/XLSX/XLSM/Parquet ingestion truth | REPLACE | LAC Data Bridge |
| Shape, schema, missing, duplicates, summaries, date ranges | KEEP + EXTEND | LAC |
| Statistics, DuckDB, business and NPL analytics | KEEP | LAC |
| SQL security, workspace jail, audit and approval | KEEP | LAC |
| Excel/PDF/HTML generation and validation | KEEP + HARDEN | LAC |
| Local Quick interpretation | BUILD | LAC + Ollama |
| Analyst pipeline | BUILD | LAC typed findings feeding Hermetic composer |
| Local Investigate | REPLACE | Controlled planner/executor/verifier/synthesizer |
| Company/user/experience memory separation | BUILD | LAC |
| SSO, Kubernetes, multi-node GPU | DEFER | Post-stable release |

## Why the boundary is HTTP

- The Python analytics core stays independently testable and usable by CLI.
- Python and TypeScript remain independently testable even though their sources ship together.
- Both services remain localhost-only and can be packaged as desktop sidecars later.
- A versioned contract prevents UI schema drift from changing analytical meaning.
- The previous Hermetic fork is now a reference/history source, not a runtime or clone dependency.

## Bridge API v1

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Data Bridge and local Ollama readiness |
| `POST /api/v1/datasets/upload` | Chunked local upload, signature validation, manifest/profile |
| `GET /api/v1/datasets/manifest` | Deterministic CSV dialect or Excel sheet discovery |
| `POST /api/v1/datasets/profile` | Deterministic profile for an existing workspace file |
| `POST /api/v1/analysis/quick` | Profile plus optional local-Qwen interpretation |
| `POST /api/v1/analysis/analyst` | Deterministic target-aware statistics and verifier |
| `POST /api/v1/analysis/agent` | Bounded local planner, typed tools, verifier and synthesis |
| `GET/DELETE /api/v1/analysis/history/...` | Local verified-finding archive and deletion |
| `POST /api/v1/analysis/analyst/report/...` | Verified Excel, HTML and PDF reports |

Browser access is limited to configured localhost/Tauri origins. The existing optional API token
continues to protect every `/api/` route when enabled.

## Finding contract

Every authoritative number should have a stable `finding_id`. Milestone 1 establishes:

- `profile.shape.rows`
- `profile.shape.columns`
- `profile.quality.missing_cells`
- `profile.quality.exact_duplicate_copies`

The UI may format these values, but it must not recalculate or relabel them into a different KPI.
Qwen receives a bounded profile digest without raw rows and must cite supplied finding IDs when it
states a number.

## Milestones

### Milestone 1 — deterministic local quick path

- Windows double-click launcher
- Ollama and Docker readiness checks
- CSV encoding/delimiter/decimal/quote detection
- XLSX/XLSM sheet and header discovery
- XLSX/XLSM archive decompression and entry-count guards
- no silent malformed-file acceptance
- deterministic profile and typed findings
- optional local Qwen interpretation
- regression contract: 1,508 rows, 22 columns, 52 missing cells, 8 duplicate copies

### Milestone 2 — analyst pipeline

Profile → semantic KPI selection → statistics → typed findings → verifier → dashboard →
Excel/PDF/HTML validation → Qwen explanation.

### Milestone 3 — controlled local Investigate

Planner → bounded typed tools → executor → deterministic verifier → tool-less final synthesis.
Required controls include duplicate-call blocking, failure budget, goal completion, evidence binding,
and a guaranteed final-answer reserve.

The bounded planner/runtime, Agent API/UI and adversarial suite are implemented. Milestone 3 remains
partial until a live local-Ollama Agent run and the packaged Windows Tauri path pass physical E2E.

## Non-negotiable release rules

- `main` remains the RC1 line until acceptance is complete.
- No invented KPI, company rule, benchmark, validation result, or generated file claim.
- No stable release without a real Windows end-to-end run.
- Source files are never modified during profiling.
- Direct user uploads are local; agent-requested writes continue through the approval policy.
