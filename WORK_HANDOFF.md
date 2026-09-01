# Work Handoff

Updated: 2026-09-01

Canonical repository: `Blacksidemre/local-analytics-copilot`

Development branch: `hermetic-hybrid-integration`

Release status: **pre-release — physical Windows acceptance pending**

## Git and governance

- The first canonical product promotion was merged through protected-branch PR #4.
- Promotion method: normal merge commit; no force push, history rewrite or direct ruleset bypass.
- Promoted `main` checkpoint: `d201f197d17873b7a7b0f36013e81ae3e5cde56e`.
- Main GitHub Actions Run 27 passed all five required jobs.
- Follow-up history/comparison and documentation cleanup is developed on the integration branch and
  must pass its PR CI before the next protected `main` merge.
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
Python regression: 125 passed, 1 skipped (PowerShell unavailable)
Python coverage: 75.74% (required 60%)
Python sdist/wheel: PASS
Python dependency check: PASS

History/Agent API targeted Python: 7 passed
Desktop bridge/history + UI targeted Vitest: 34 passed
Desktop TypeScript: PASS
Modified desktop ESLint: PASS
Desktop/root Prettier: PASS
git diff --check: PASS
```

The Next production build compiled successfully and entered its post-compile checks locally, but the
managed environment stopped the process when an inherited provider path attempted a prohibited
network/metadata probe. The broad inherited desktop test inventory was stopped for the same safety
reason. This was not bypassed. The changed bridge/UI tests are green; the clean GitHub Actions
desktop-contract build and selected offline tests are the authoritative final gate.

Rust/Cargo and physical Windows are unavailable in this Linux workspace. The last promoted main CI
passed Windows Tauri `cargo check --locked` plus packaged backend executable health smoke, but those
checks do not prove a physically installed desktop application.

## Remaining release blockers

1. Integration candidate and follow-up protected `main` PR CI must be green.
2. Run controlled CSV and XLSX Agent requests with the configured real local Ollama model.
3. Install Visual Studio Build Tools (`Desktop development with C++`), MSVC and Windows SDK.
4. Run physical Tauri startup, upload, Agent, verifier, report and shutdown acceptance.
5. Build the Windows installer and pass clean install, shortcut launch, upgrade and uninstall.

## Minimum later Windows acceptance

From only the canonical repository:

```powershell
git switch main
git pull
pnpm desktop:install
pnpm desktop:dev
```

Upload the controlled CSV and XLSX fixture, run one natural-language Agent request on each, confirm
the verifier passes and download one verified report. After developer E2E passes, run
`pnpm desktop:build` and execute the installer checklist. No second repository or second terminal is
required.

Do not publish stable `v1.0.0` until every physical gate in `docs/RELEASE_CHECKLIST.md` is evidenced.
