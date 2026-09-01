# Release Checklist

Status: **pre-release — stable v1.0.0 is blocked**

This checklist is the release gate for the canonical single-repository product. A checked source or
CI item does not replace physical Windows acceptance.

## 1. Source and governance

- [x] Canonical repository is `Blacksidemre/local-analytics-copilot`.
- [x] End users do not need the old Hermetic fork.
- [x] `main` is protected against deletion and non-fast-forward updates.
- [x] Main promotion uses PR/clean merge; no history rewrite or force push.
- [x] Root MIT license is present.
- [x] Hermetic-derived MIT license and original copyright are retained.
- [x] Vendored Apache-2.0 license/NOTICE and font attribution are retained.
- [x] `.env`, workspace data, reports, logs and SQLite state are excluded from Git.
- [ ] Select final pre-release version after physical acceptance; do not tag `v1.0.0` yet.

## 2. Deterministic analytics and evidence

- [x] CSV and XLSX ingestion use the same typed contract.
- [x] Missing and duplicate-copy semantics are deterministic.
- [x] Analyst numeric findings carry stable `finding_id` and source.
- [x] Statistical tests include effect-size/multiple-testing handling where applicable.
- [x] Association is not represented as causality.
- [x] Business/KPI meaning requires supplied or approved metadata.
- [x] Verifier failure prevents trusted model prose from being shown.
- [x] Excel/HTML/PDF reports preserve a shared verified manifest.
- [x] Output files are reopened and validated.

## 3. Bounded Agent

- [x] Local Ollama planner uses typed/bounded plans.
- [x] Only allowlisted deterministic analytic tools execute.
- [x] Tool budget, failure budget, duplicate-call and loop guards are active.
- [x] Arbitrary Python/shell/PowerShell/SQL/filesystem/internet/raw-row operations are unavailable.
- [x] Fake IDs/evidence and unsupported numeric/KPI/causality/prediction claims fail closed.
- [x] Adversarial regression suite covers prompt injection and tool-abuse classes.
- [ ] Run controlled CSV Agent acceptance with a real local Ollama model on Windows.
- [ ] Run equivalent XLSX Agent acceptance and verify parity.

## 4. Local history and privacy

- [x] Only verifier-passed bounded evidence may be archived.
- [x] History can be listed, opened and deleted.
- [x] Raw rows, prompts, secrets and unverified prose are not retained.
- [x] Archived evidence is not automatically promoted into a new run.
- [x] Two verifier-passed manifests can be compared deterministically from the desktop UI.
- [x] Added/removed/incompatible findings are explicit and period semantics are not inferred.

## 5. CI and package checks

- [x] Python 3.11 and 3.12 unit/regression suites.
- [x] Windows Python smoke and privacy check.
- [x] Ruff format/lint, package build and dependency check.
- [x] Desktop TypeScript, Vitest, ESLint and format checks.
- [x] Offline Next production build.
- [x] Canonical launcher contract.
- [x] Windows Tauri Rust `cargo check --locked`.
- [x] PyInstaller backend executable build and `/health` smoke.
- [ ] Build signed/unsigned pre-release installer artifact on Windows.
- [ ] Verify installer artifact checksum and bundled LICENSE/NOTICE files.

## 6. Physical Windows acceptance

- [ ] Visual Studio Build Tools, MSVC and Windows SDK installed.
- [ ] `pnpm desktop:dev` opens the native desktop app.
- [ ] Backend/UI use loopback-only dynamically managed ports.
- [ ] Startup handles existing services and port conflicts cleanly.
- [ ] Exit removes only child processes started by the application.
- [ ] Ollama installed/running/model-missing states show recoverable guidance.
- [ ] Model unavailable still permits deterministic Quick/Analyst.
- [ ] Controlled CSV and XLSX produce expected verified results.
- [ ] Agent report downloads open and contain matching evidence.
- [ ] Clean installer install, desktop shortcut, launch, upgrade and uninstall pass.
- [ ] Config, logs and workspace land in the intended user-local application-data location.

## 7. Release decision

Stable release is allowed only when:

- all required CI jobs are green on the exact candidate commit;
- every physical acceptance item above is evidenced;
- known regressions are triaged;
- README/CHANGELOG/WORK_HANDOFF reflect the candidate accurately;
- no stable claim is made for an untested installer or model path.

Current decision: **NO-GO for stable v1.0.0; GO for continued pre-release testing.**
