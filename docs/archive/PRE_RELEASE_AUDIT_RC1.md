# Historical Pre-release Audit — 1.0.0rc1

> **Archived/deprecated.** This audit predates the canonical desktop/Agent consolidation. Use
> [`docs/PRE_RELEASE_AUDIT.md`](../PRE_RELEASE_AUDIT.md) for current status.

Audit date: 2026-08-29

## Decision

The existing deterministic analytics core is suitable for hardening; a full rewrite is not justified.
The first GitHub milestone is a release candidate, not a stable/final release.

## Verified release gate

- SHA-256 and ZIP integrity of the inherited source package were verified before editing.
- Editable installation succeeds on Python 3.12.
- `ruff format --check .` passes.
- `ruff check .` passes.
- Python source compilation passes.
- 35 automated tests pass.
- Measured source coverage is 61.83%.
- Wheel and source-distribution builds pass.
- The built wheel installs into a fresh virtual environment; CLI, packaged defaults and health/privacy
  smoke checks pass without using the source tree.
- `pip check` reports no broken installed requirements.
- FastAPI health, API-token enforcement, security headers and exact-action approval were exercised.
- Deterministic CSV, DuckDB, Excel, statistics, business and NPL paths were exercised.

## Security findings closed for RC1

- Dataset SQL can no longer call DuckDB file/network scanners or query arbitrary tables.
- SQL validation uses an AST parser and rejects multiple statements, DML and DDL.
- Agent-requested workspace writes and web calls are queued for human approval.
- Approval executes the stored tool name and exact canonical arguments once.
- Remote Ollama endpoints and cloud model tags are blocked by default.
- Non-loopback UI binding requires an explicit opt-in and an API token.
- Excel string-to-formula and string-to-URL conversion is disabled.
- Output helpers avoid silently overwriting prior reports.
- Workspace knowledge files, SQLite state, logs and outputs are excluded from Git.
- Audit payloads redact common token/PII patterns and cap logged strings.
- Retrieved documents and tool content are explicitly treated as untrusted prompt data.

## Correctness findings closed for RC1

- Unequal-variance normal groups route to Welch ANOVA instead of classical ANOVA.
- PCA/clustering/ML/bootstrap/Monte Carlo edge inputs are validated.
- Vintage analysis honors the portfolio dimension.
- Roll-rate analysis reports optional balance-weighted migrations.
- Valuation scenarios reject invalid rates/prices and bound scenario grids.
- Funnel zero-denominator, empty RFM and negative Pareto inputs are handled explicitly.

## Target-machine checks still required

These cannot be certified in the Linux build environment:

- Windows 11 installation through `scripts/install_windows.ps1`.
- RTX 5070 Ti VRAM/RAM use and tokens/second.
- `qwen3.5:9b` and optional `gpt-oss:20b` tool-call reliability through real Ollama.
- Native Microsoft Excel COM PivotTable creation.
- Live PostgreSQL/SQL Server behavior using genuinely read-only accounts.
- Optional OCR/Tesseract.
- OpenClaw provider configuration and end-to-end action approval.

Stable `v1.0.0` should not be tagged until the target-machine checklist passes and discovered issues are
triaged. See `docs/FINAL_HANDOFF.md` for the run order.
