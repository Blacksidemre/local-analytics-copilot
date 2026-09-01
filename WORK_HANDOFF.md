# Work Handoff

Updated: 2026-09-01

Branch: `hermetic-hybrid-integration`

Canonical repository: `Blacksidemre/local-analytics-copilot`
Protected branches: `main` and upstream `achalp/hermetic` were not changed

## Published integration checkpoints

- Canonical single-repository consolidation checkpoint: `64c709d` on
  `Blacksidemre/local-analytics-copilot:hermetic-hybrid-integration`.
- Verified Agent evidence-report checkpoint: `d270d4a`.
- Current CI-green product checkpoint: `3a29916`; GitHub Actions CI Run 26 completed successfully
  with all five jobs passing.
- Historical Hermetic UI checkpoint: `3fe0afb` on
  `Blacksidemre/hermetic:lac-data-bridge-integration`.
- The canonical repository tree was verified byte-for-byte against the locally tested tree before
  the branch ref was advanced.

## Current product state

The product source is now consolidated in one repository. The deterministic Python analytics,
reporting and Agent services remain under `src/lacopilot`; the Hermetic-derived Next/Tauri product
shell is preserved under `apps/desktop`. Original MIT and Apache-2.0 notices remain in place.

The runtime boundary is intentionally still two localhost processes inside one product:

```text
Local Analytics Copilot launcher / Tauri
  -> trusted same-origin UI proxy
  -> LAC Data Bridge + deterministic analytics + verifier
  -> local Ollama planner/synthesizer (optional; never authoritative for calculations)
```

The old `Blacksidemre/hermetic` integration branch is a historical/reference source after this
consolidation; end users no longer need to clone it.

## Milestone status

- Milestone 1 — deterministic CSV/XLSX Quick path: **PASS for browser path**. The user's prior
  physical Windows tests confirmed `1508 x 22`, 52 missing cells and 8 exact duplicate copies.
- Milestone 2 — deterministic Analyst, verifier and Excel/HTML/PDF reports: **PASS for browser
  path**. The user's prior physical Windows test confirmed Analyst verification and report output.
- Milestone 3 — bounded local Agent: **PARTIAL**. Planner/runtime, Agent API/UI, adversarial suite,
  verified synthesis and local history foundation are implemented. A live local-Ollama Agent run
  and packaged Windows Tauri E2E are still required before PASS.

## Bounded Agent capabilities

`POST /api/v1/analysis/agent` implements:

- local Ollama JSON-schema planner with a maximum of six steps;
- allowlisted typed tools only: dataset profile, target association screen, numeric description,
  category frequency, segment aggregation, time trend and outlier screening;
- duplicate-call/loop guard, dependency checks, failure budget and goal completion;
- independent deterministic tool/run verification and stable `finding_id` evidence;
- bounded tool-less synthesis from verified evidence only;
- no arbitrary Python, shell, PowerShell, SQL, filesystem traversal, internet or raw-row dump;
- fail-closed behavior for fake evidence, unsupported numeric claims, causality, prediction,
  unapproved business/KPI meaning and prompt injection in dataset values;
- deterministic Quick Dashboard fallback when Ollama/planner is unavailable.

Verifier-passed Agent runs now have evidence-only Excel, HTML and PDF exports through
`POST /api/v1/analysis/agent/report`. All three formats use the same archived finding manifest and
SHA-256 digest, are reopened and validated before download, and exclude raw rows and unverified
model prose. Formula injection, scripts/external resources, duplicate or altered evidence and
unverified history fail closed.

The Agent UI shows the active dataset, optional explicit target semantics, plan steps, progress,
verified evidence, verifier result, safe synthesis, evidence-report downloads and recoverable
local-model errors.

## Local model management

Bridge health reports installed Ollama models, the configured default and whether it is present.
The UI offers an installed-model selector and passes the selection through Quick, Analyst, Agent
and report requests. If no model is available, deterministic Quick/Analyst calculations remain
usable; unverified model prose is never presented as trusted output.

## Memory and history foundation

Verified Agent runs can be stored in local `workspace/analysis_history.sqlite3` and can be listed,
opened or deleted through typed API routes. Storage keeps only the dataset-local fingerprint,
request summary, used tool names and a maximum of 48 verifier-passed findings. It does not retain
raw rows, model prompts, tool arguments or secrets, and archived findings are not automatically
promoted to evidence for a later run. The report endpoint projects only an explicitly requested,
verifier-passed archived run; it does not rerun a tool or reopen the dataset.

Company rules still follow the existing candidate -> explicit human approval -> approved memory
flow. Full cross-session conversational/project-history UX and period comparison remain future
work; the current storage layer is deliberately a safe foundation rather than autonomous memory.

## Canonical launcher and desktop packaging

- Root `pnpm dev` starts and supervises the backend plus unified web UI.
- Root `pnpm desktop:dev` starts the backend and Tauri development shell.
- Commands use relative paths, loopback-only ports, service-identity probes and bounded waits.
- The launcher refuses unrelated services on required ports, reuses healthy existing services and
  kills only child processes it started.
- `Start_Local_Analytics_Copilot.cmd` / `scripts/launch_windows.ps1` start the unified browser UI
  and preserve the previously verified Windows UTF-8, Ollama and Docker-off behavior.
- Release Tauri code allocates ephemeral loopback ports, generates a per-run API token, stores
  workspace/config/logs under the application data directory and ties backend/UI children to the
  app lifecycle.
- The deterministic backend has a PyInstaller one-directory build path and is bundled as a Tauri
  resource. Windows CI builds and smoke-tests that executable.
- Native build prerequisites are checked with an actionable Visual C++/Windows SDK message.

## License and attribution

- LAC root license: MIT.
- Hermetic-derived source: `apps/desktop/LICENSE` (MIT, original copyright retained).
- Vendored json-render: `apps/desktop/src/spec/LICENSE` and `NOTICE.md` (Apache-2.0).
- Consolidated notice index: `THIRD-PARTY-NOTICES.md`.

## Latest local validation

```text
Python suite excluding the known local Polars and DuckDB binary crashes:
  121 passed, 1 skipped (PowerShell absent), 2 deselected
  coverage 74.71% (required minimum 60%)

Agent/history/report/API targeted tests:
  8 passed

Canonical launcher + packaging contract:
  7 passed

Desktop formatting:
  PASS

Desktop ESLint:
  PASS with 47 inherited warnings, 0 errors

Desktop TypeScript:
  PASS

Desktop bridge/UI/proxy/launcher Vitest:
  48 passed

Offline production font contract:
  PASS (no build-time Google Fonts request)

Canonical Next production build:
  PASS (69 routes/pages, telemetry and network proxies disabled)

Python sdist/wheel + dependency check:
  PASS

git diff --check:
  PASS

GitHub Actions CI Run 26 on 3a29916:
  PASS (5/5 jobs)
  Linux Python 3.11 + 3.12
  Windows Python smoke + privacy check
  Desktop contracts + production build
  Windows Tauri cargo check
  Packaged Windows backend executable + health smoke
```

The transient Linux environment's installed `polars` and `duckdb` native modules terminate with a
CPU `Bus error` in their two execution tests. The remainder of the suite passes when those two
known tests are deselected; GitHub Linux/Windows jobs run the complete suite on clean runners.

The canonical Next production build passes with an in-tree dependency tree. Geist and Geist Mono
are bundled from the existing `@fontsource-variable` packages, so an offline build no longer makes
a Google Fonts request.

The complete inherited Hermetic Vitest inventory was not run to completion in this managed
workspace because one unrelated cloud-credential test attempted to contact
`metadata.google.internal` and was blocked by the environment security boundary. The canonical
CI-selected bridge, Agent UI, proxy, launcher and offline-build tests all passed without network
access.

Rust/Cargo and PyInstaller are not installed in this Linux workspace. GitHub's Windows runner
successfully completed `cargo check --locked`, built the packaged backend and passed its executable
health smoke on `3a29916`. This is still not a claim that the final installed Tauri application
passed on the user's physical Windows machine.

## Remaining release blockers

1. Run one real local-Ollama Agent request on controlled CSV and XLSX and confirm verified output.
2. Install Visual Studio Build Tools (`Desktop development with C++`, MSVC and Windows SDK) and
   complete the physical `pnpm desktop:dev` Tauri acceptance.
3. Build and test the Windows installer/package on the physical target machine.
4. Add fuller history/project comparison UX before stable v1.0 if it is considered a release
   requirement rather than post-v1 scope.

## Minimum later Windows acceptance

From only the canonical LAC repository:

```powershell
git switch hermetic-hybrid-integration
git pull
pnpm desktop:install
pnpm desktop:dev
```

Then upload the controlled CSV and XLSX fixture, run one natural-language Agent request, confirm
the verifier passes, and download one report. No second repository or second terminal is required.

Do not merge to `main` or publish a stable release until this physical native path passes.
