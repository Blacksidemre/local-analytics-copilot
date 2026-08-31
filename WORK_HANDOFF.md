# Work Handoff

Updated: 2026-08-31

Branch: `hermetic-hybrid-integration`

Canonical repository: `Blacksidemre/local-analytics-copilot`
Protected branches: `main` and upstream `achalp/hermetic` were not changed

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

The Agent UI shows the active dataset, optional explicit target semantics, plan steps, progress,
verified evidence, verifier result, safe synthesis and recoverable local-model errors.

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
promoted to evidence for a later run.

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
  118 passed, 1 skipped (PowerShell absent), 2 deselected

Agent/history/API targeted tests:
  PASS

Canonical launcher + packaging contract:
  7 passed

Desktop formatting:
  PASS

Desktop ESLint:
  PASS with 47 inherited warnings, 0 errors

Desktop TypeScript:
  PASS

Desktop bridge/UI/proxy/launcher Vitest:
  43 passed

git diff --check:
  PASS
```

The transient Linux environment's installed `polars` and `duckdb` native modules terminate with a
CPU `Bus error` in their two execution tests. The remainder of the suite passes when those two
known tests are deselected; GitHub Linux/Windows jobs run the complete suite on clean runners.

The local Next production build cannot be used as a release signal in this workspace because
`apps/desktop/node_modules` is an ignored symlink to the separately checked-out Hermetic dependency
tree; Turbopack correctly rejects a symlink outside the project filesystem root. The canonical CI
performs a fresh in-tree `pnpm install` and production build.

Rust/Cargo and PyInstaller are not installed in this Linux workspace. Windows CI therefore owns
the Rust `cargo check --locked`, packaged-backend build and executable health smoke. This is not a
claim that the final installed Tauri application passed on the user's physical Windows machine.

## Remaining release blockers

1. GitHub Actions for the consolidation commit must be green.
2. Run one real local-Ollama Agent request on controlled CSV and XLSX and confirm verified output.
3. Install Visual Studio Build Tools (`Desktop development with C++`, MSVC and Windows SDK) and
   complete the physical `pnpm desktop:dev` Tauri acceptance.
4. Build and test the Windows installer/package on the physical target machine.
5. Add Agent-native report export and fuller history/project comparison UX before stable v1.0 if
   they are considered release requirements rather than post-v1 scope.

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
