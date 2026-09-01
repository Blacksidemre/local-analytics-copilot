# Work Handoff

Updated: 2026-09-01

Canonical repository: `Blacksidemre/local-analytics-copilot`

Development branch: `hermetic-hybrid-integration`

Release status: **pre-release — physical Windows acceptance pending**

## Git and governance

- The canonical product and the verified history/comparison follow-up were merged through protected
  branch pull requests; no direct protected-branch write was used.
- Promotion method: normal merge commit; no force push, history rewrite or direct ruleset bypass.
- Release acceptance was promoted through protected-branch PR #8 using a normal merge commit.
- Current promoted `main` checkpoint: `b392134964147e8f074ca38cdbc6b3a8232bf00e`.
- PR GitHub Actions Run 40 and main GitHub Actions Run 41 each passed all five required jobs.
- Release-acceptance integration checkpoint: `e7e39003b7fd45b3e755f279eeef3108ede729f7`.
- The old `Blacksidemre/hermetic` repository is historical/reference only. It is not a runtime,
  build or package dependency and receives no new product work.
- `achalp/hermetic` remains read-only; no PR, issue or write was sent upstream.

## Canonical product

One repository contains:

- `apps/desktop`: Hermetic-derived Next.js/Tauri product shell;
- `src/lacopilot`: deterministic ingestion, analytics, bounded Agent, verifier, reports and history;
- `scripts`: canonical web/desktop launch and packaged-backend build entries;
- `tests`: CSV/XLSX, Agent/adversarial, verifier, reporting, history and launcher regression.

Root MIT, Hermetic-derived MIT, vendored Apache-2.0 and font attribution are preserved in `LICENSE`,
`apps/desktop/LICENSE`, `apps/desktop/src/spec/LICENSE`, `apps/desktop/src/spec/NOTICE.md` and
`THIRD-PARTY-NOTICES.md`.

## Milestones

- Milestone 1 — deterministic CSV/XLSX Quick path: **PASS**.
- Milestone 2 — deterministic Analyst, verifier and Excel/HTML/PDF reports: **PASS**.
- Milestone 3 — bounded local Agent: **PARTIAL**.

Milestone 3 remains PARTIAL only because the exact candidate still needs controlled CSV/XLSX Agent
runs with a real local Ollama model and physical packaged Windows/Tauri acceptance. Repository-side
Agent implementation and automated adversarial/evidence gates are present.

## Agent and reports

`POST /api/v1/analysis/agent` provides a local Ollama JSON-schema planner, maximum six-step typed
plan, allowlisted deterministic tools, dependency validation, failure budget, duplicate-call/loop
guard, stable finding evidence, independent verifier and bounded tool-less synthesis.

There is no arbitrary Python, shell, PowerShell, SQL, filesystem, internet or raw-row-dump Agent
tool. Fake IDs/evidence, unsupported numbers, invented business/KPI meaning and
association-to-causality/prediction claims fail closed. Model-unavailable cases retain deterministic
Quick/Analyst operation.

Verifier-passed Agent runs can generate Excel, HTML and PDF from one archived evidence manifest.
All formats share the same SHA-256 binding and numeric findings, are reopened for validation and
exclude raw rows and unverified model prose.

The Analyst Excel workbook now embeds the same verified evidence manifest SHA-256 used by HTML and
PDF in its package metadata. Reopen validation rejects a removed or changed workbook binding.

## History and deterministic comparison

- Verifier-passed Agent runs can be listed, opened and explicitly deleted in the desktop UI.
- Storage is local SQLite and bounded to dataset fingerprint, safe request summary, used typed tools
  and at most 48 verified findings.
- Raw rows, internal model prompts, tool arguments, secrets and unverified prose are not archived.
- Two different verifier-passed manifests can be compared without reopening raw data.
- Only matching `finding_id`, kind, unit, deterministic source and dimension contracts receive
  numeric deltas; changed/unchanged/added/removed/incompatible states are explicit.
- Period and business meaning remain `not_inferred`; the user selects baseline/current order.
- Archived findings are never promoted automatically into a current run.

## Launcher and Windows packaging preparation

- Root `pnpm dev` supervises the deterministic backend and unified web UI.
- Root `pnpm desktop:dev` supervises the backend and Tauri development shell.
- Paths are repository/resource relative; services bind loopback only.
- Launchers detect unrelated port occupants, reuse only identity-verified services and clean up only
  owned child processes.
- Release Tauri uses ephemeral ports, per-launch API token, packaged Node UI sidecar and PyInstaller
  backend resource.
- Config/log/workspace directories resolve under user-local application data in packaged mode.
- Missing Rust/Visual C++ Build Tools/MSVC/Windows SDK produces actionable prerequisite guidance.
- Ollama/model absence is recoverable; deterministic modes remain available.

## Documentation cleanup

- Root README now describes the canonical single-repository pre-release product.
- Current architecture, build status, product plan, privacy/offline behavior and release checklist
  reflect Quick → Analyst → bounded Agent.
- Pre-consolidation RC1/Hermetic documents are moved under `docs/archive` or explicitly marked
  historical/deprecated.
- Stable `v1.0.0` and production installer claims remain blocked.

## Latest local validation

```text
Python Ruff format/lint: PASS
Release acceptance + Analyst targeted regression: 17 passed
Excel manifest tamper + report/acceptance targeted regression: 4 passed
Python broad regression before optional-native install: 126 passed, 1 skipped, 1 environment failure
Python coverage: 75.69% (required 60%)
Python sdist/wheel: PASS
Python dependency check: PASS
Release acceptance offline mode: PASS with live-Agent skip
git diff --check: PASS
```

The broad regression's only failure was caused by the isolated environment initially lacking the
optional DuckDB package. Installing the optional DuckDB/Polars/PyArrow wheels then reproduced the
known managed-runtime native CPU `Bus error` on import, before test code could execute. This is an
environment blocker, not hidden as a pass; clean GitHub Linux/Windows runners remain authoritative.

Rust/Cargo and physical Windows are unavailable in this Linux workspace. The last promoted main CI
passed Windows Tauri `cargo check --locked` plus packaged backend executable health smoke, but those
checks do not prove a physically installed desktop application.

## Remaining release blockers

1. Run controlled CSV and XLSX Agent requests with the configured real local Ollama model.
2. Install Visual Studio Build Tools (`Desktop development with C++`), MSVC and Windows SDK.
3. Run physical Tauri startup, upload, Agent, verifier, report and shutdown acceptance.
4. Build the Windows installer and pass clean install, shortcut launch, upgrade and uninstall.

## Minimum later Windows acceptance

From only the canonical repository:

```powershell
git switch main
git pull
pnpm desktop:install
.\scripts\run_release_acceptance.ps1 -LiveAgent
pnpm desktop:dev
```

The acceptance command generates its own controlled CSV/XLSX, verifies deterministic parity and
reports, and requires the live local Agent chain. Then use `pnpm desktop:dev` for the physical native
window/lifecycle check. After developer E2E passes, run `pnpm desktop:build` and execute the installer
checklist. No second repository or second terminal is required.

Do not publish stable `v1.0.0` until every physical gate in `docs/RELEASE_CHECKLIST.md` is evidenced.
