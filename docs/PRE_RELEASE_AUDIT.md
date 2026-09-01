# Pre-release Audit — Canonical Local Analytics Copilot

Audit date: 2026-09-01

## Decision

The consolidated product is suitable for continued pre-release acceptance. The canonical source is
`Blacksidemre/local-analytics-copilot`; the old Hermetic fork is historical/reference only.

This audit does **not** approve stable `v1.0.0`, claim production readiness, or certify the physical
Windows installer path.

## Verified repository gates

- `main` was promoted through its protected-branch pull-request ruleset without force push or
  history rewrite.
- The promoted tree is identical to the reviewed `hermetic-hybrid-integration` tree.
- GitHub Actions validates Linux Python 3.11/3.12, Windows Python/privacy, desktop contracts,
  production Next build, Windows Tauri `cargo check --locked`, packaged backend build and executable
  health smoke.
- Canonical source, launchers, analytics backend, Agent, history and UI live in one repository.
- No runtime/package dependency on `Blacksidemre/hermetic` or `achalp/hermetic` remains.
- Root MIT, Hermetic-derived MIT, vendored Apache-2.0 and font attribution files are retained.
- Production secret-pattern and tracked credential/private-data filename scans are clean.

## Verified product gates

- Milestone 1: deterministic CSV/XLSX ingestion and Quick profile — PASS.
- Milestone 2: Analyst statistics, typed findings, verifier and Excel/HTML/PDF reports — PASS.
- Milestone 3: bounded local Agent — PARTIAL.
- Agent planner has typed/allowlisted tools, tool/failure budgets, duplicate-call/loop guards and
  deterministic evidence verification.
- Unsupported numeric, business/KPI, causality and prediction claims fail closed.
- Verified Agent Excel/HTML/PDF reports share one archived evidence manifest and SHA-256 binding.
- Local history stores bounded verifier-passed evidence without raw rows, prompts or secrets.
- Local history UI lists, opens and explicitly deletes runs; two verifier-passed manifests can be
  compared without reopening raw data or inferring period/business meaning.

## Physical acceptance still required

1. Run a real local-Ollama Agent request against controlled CSV and XLSX on the target Windows PC.
2. Install Visual Studio Build Tools with Desktop development with C++, MSVC and Windows SDK.
3. Run the physical Tauri path and confirm upload, Agent, verifier, report download and shutdown.
4. Build the Windows installer and validate clean install, launch, upgrade and uninstall.

Until these pass, repository and UI wording must remain **pre-release / physical Windows acceptance
pending**.

## Known environment limitation

The managed Linux development environment may terminate in two native Polars/DuckDB execution tests
with a CPU `Bus error`. This is documented rather than hidden; clean GitHub Linux and Windows runners
execute the full suite and are the authoritative regression gate.

See [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) and root [`WORK_HANDOFF.md`](../WORK_HANDOFF.md).
