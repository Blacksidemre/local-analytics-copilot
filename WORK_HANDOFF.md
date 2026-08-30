# Work Handoff

Updated: 2026-08-30
Branch: `hermetic-hybrid-integration`
Baseline: `cfbc2e2` (`main` and branch were identical before hybrid work)
Last validated revision: the current branch HEAD containing this document

## Completed milestone

Milestone 1 backend/bridge and browser UI paths passed on the user's Windows machine. The native
Tauri window remains a separate physical acceptance item because Visual C++ Build Tools/link.exe is
not installed; no desktop E2E success is inferred from browser or CI results.

- Hybrid boundary frozen in `docs/HYBRID_ARCHITECTURE.md`.
- Hermetic upstream `04e4dca` inspected; current Tauri and XLSX/sheet-picker work is BORROW.
- LAC deterministic Data Bridge now owns CSV/XLSX/XLSM/Parquet ingestion truth.
- CSV detection covers encoding, delimiter, quote, decimal and thousands separators.
- Excel discovery covers sheet names and header-row detection.
- XLSX/XLSM ZIP archives are bounded by declared uncompressed size and entry count before parsing.
- Malformed CSV, fake/corrupt Excel, wrong signatures and unsupported types return typed errors.
- Upload API writes in bounded chunks under `workspace/incoming` and never overwrites a source.
- Profiles expose schema, roles, missing, unique counts, duplicates, summaries and date ranges.
- Authoritative profile numbers have stable `finding_id` values.
- Quick Dashboard API payload selects KPI cards only by stable `finding_id`, preserves each
  deterministic calculation source and contains no raw rows.
- CSV and XLSX regression fixtures now verify the same dashboard card and missing-column contract.
- Hermetic bridge errors normalize to `{ code, message, hint, details }` for typed UI handling.
- Quick mode can ask local Ollama to interpret a bounded profile digest without raw rows and reports
  numeric-evidence and semantic verification separately from deterministic analytics.
- Dataset-wide missing rate and every column-level missing percentage have separate stable finding
  IDs; column percentages cannot be added and presented as a dataset-wide rate.
- Duplicate-copy removal count is explicitly separated from duplicate-group rows including
  originals. Binary columns carry no inferred target/probability/business meaning.
- Qwen text that fails numeric binding or the duplicate/missing/binary semantic guardrails is
  rejected and is not returned to the UI as trusted interpretation.
- Windows double-click launcher supports `py -3.12` when the `python` alias is broken.
- Windows native probes now allow expected non-zero results, Docker-off is a warning, and console
  plus Python subprocess output are configured for UTF-8.
- Hermetic adapter client and integration sequence live under `integrations/hermetic/`.

## Milestone 2 current slice

The first bounded Analyst vertical slice is implemented:

- `POST /api/v1/analysis/analyst` requires an explicit target column.
- Non-binary targets require an explicit statistical kind; column names never establish business
  meaning.
- Identifier, datetime and free-text fields are excluded from automatic predictor selection.
- Binary, continuous and categorical target screens dispatch deterministic Mann-Whitney,
  Spearman, Kruskal-Wallis, chi-square or Fisher tests as appropriate.
- Raw p-values are adjusted together with Benjamini-Hochberg correction.
- Effect, raw p-value, adjusted p-value and complete-case count each receive stable `finding_id`
  evidence.
- The Analyst verifier rejects duplicate/unknown/orphan findings, broken analysis-to-finding ID
  chains, dimension/unit/source drift, invalid observation counts, incorrect recomputed
  Benjamini-Hochberg values, reordered dashboard cards and invented target/KPI semantics.
- The Hermetic bridge revalidates the Analyst contract before rendering it.
- The hybrid UI now lets the user explicitly select a target and target kind, then displays only
  verifier-passed effect cards and method metadata.
- Local Qwen receives only the bounded top-card Analyst digest, never raw rows. Numeric statements
  must cite matching Analyst findings; unsupported causal, predictive, significance, risk and
  business-importance claims are rejected and hidden from the UI.
- A verified Analyst Excel report is now generated from that manifest with four sheets:
  `Executive Dashboard`, `Associations`, `Evidence`, and `Methodology`. Dashboard values are
  direct formulas into the Evidence sheet; raw rows are never exported.
- The backend reopens every generated report and rejects it if sheets, finding values/sources,
  formulas, cached formula values, error cells, or external-link checks fail.
- Hermetic exposes the report as a one-click verified `.xlsx` download through the loopback-only
  bridge proxy.
- Self-contained HTML and PDF reports are generated from the same verifier-passed finding
  manifest. Both formats include the stable finding IDs and a SHA-256 evidence-manifest binding;
  neither format exports raw source rows or loads external resources.
- HTML verification rejects missing sections, altered values/units/sources, scripts and external
  links. PDF verification reopens the file, checks metadata, pages, evidence text, manifest hash,
  file links and the target/KPI guardrails.
- Hermetic now exposes verified Excel, HTML and PDF downloads. The bridge client independently
  checks each response's schema, verification headers, safe filename extension, counts and binary
  file signature before the browser can download it.

## Validation

```text
ruff format --check .                 PASS
ruff check .                          PASS
python -m compileall -q src scripts   PASS
pytest ingestion+launcher -q          20 passed, 1 skipped (pwsh absent)
node --check lac-bridge-client.ts     PASS
bridge client runtime smoke           PASS
git diff --check                      PASS
Analyst + ingestion regression        28 passed, 1 skipped (PowerShell absent)
Hermetic Analyst bridge/UI Vitest     16 passed
Hermetic TypeScript + ESLint          PASS
Analyst interpretation regression     8 passed
Hermetic interpretation bridge/UI     15 passed
Analyst Excel report regression        11 passed
Analyst document report regression      14 passed
Hermetic report bridge/proxy/UI         28 passed
Analyst workbook visual sheet pass      PASS (4 sheets)
Analyst PDF render/reopen pass           PASS (3-page controlled fixture)
LAC suite excluding local polars crash   77 passed, 1 skipped, 1 deselected
Bounded Agent CSV/XLSX regression         7 passed
LAC GitHub CI run 33336788010            PASS (Windows + Linux 3.11/3.12)
Hermetic GitHub CI run 33336825162       PASS (bridge/UI + Node 24 + Tauri + live hybrid)
Live hybrid CSV/XLSX contract            PASS (Quick + Analyst + verified XLSX/HTML/PDF)
```

The local workspace's native `polars` build still terminates with `Bus error`, but the branch's
GitHub CI completed the full coverage suite successfully on Python 3.11 and 3.12. The failure is
therefore isolated to this transient Linux runtime rather than the committed project state.

Regression fixture contract, tested for CSV and XLSX:

```text
rows                              1508
columns                             22
monthly_income_try missing          24
payment_ratio_3m missing             12
employment_years missing             16
total missing cells                  52
exact duplicate copies                8
duplicate rows including originals   16
```

## Main files changed

- `src/lacopilot/ingestion.py`
- `src/lacopilot/dataset_uploads.py`
- `src/lacopilot/quick_analysis.py`
- `src/lacopilot/analyst_pipeline.py`
- `src/lacopilot/analyst_interpretation.py`
- `src/lacopilot/analyst_report.py`
- `src/lacopilot/analyst_document_reports.py`
- `src/lacopilot/investigate_foundation.py`
- `src/lacopilot/regression_fixture.py`
- `src/lacopilot/app.py`
- `src/lacopilot/tools/common.py`
- `src/lacopilot/tools/data_tools.py`
- `tests/test_ingestion_bridge.py`
- `tests/test_analyst_pipeline.py`
- `tests/test_investigate_foundation.py`
- `scripts/launch_windows.ps1`
- `Start_Local_Analytics_Copilot.cmd`
- `integrations/hermetic/lac-bridge-client.ts`

## Known limits / blockers

- The LAC PowerShell launcher, UTF-8 output, Docker-off warning and health checks passed on the
  user's Windows machine. PowerShell is unavailable in this Linux workspace, so later launcher
  changes still rely on Windows CI plus the recorded physical result.
- Hermetic upload/Quick UI is wired on `Blacksidemre/hermetic: lac-data-bridge-integration`.
- Hermetic local Investigate remains disabled upstream. Do not remove its provider gate until the
  bounded local planner/verifier design in Milestone 3 is implemented and evaluated.
- Live Qwen, Analyst, verifier and report generation passed on the user's Windows browser path.
  Tauri-on-Windows remains blocked only by the missing Visual C++ Build Tools/link.exe prerequisite.
- GitHub's Windows runner verifies the LAC Python suite, Hermetic's Node 24 ESM launcher and that
  the Tauri Rust shell compiles. It is not evidence that the full desktop, local Ollama and Docker
  Desktop path passed interactively on the user's actual machine.
- A live contract checks both integration branches and validates controlled CSV/XLSX upload,
  Quick Dashboard evidence, Analyst verification and verified Excel/HTML/PDF downloads.
- TestClient emits one upstream Starlette/httpx deprecation warning; tests still pass.
- The complete upstream Hermetic test/build chain was stopped in this workspace when an existing
  test attempted to contact a cloud instance-metadata endpoint. No retry or bypass was attempted;
  the changed bridge/proxy/UI files passed their 28 targeted tests, formatting, ESLint and
  TypeScript checks without that access.

## Next milestone action

Milestone 2's deterministic Analyst/browser contract is frozen. A non-routable Milestone 3
foundation now defines strict local-planner schemas, user-approved target semantics, two
allowlisted deterministic tools, six-step/two-failure budgets, dependency and duplicate-call
guards, goal completion, independent profile/Analyst/run verification, no-raw-row evidence and a
48-finding tool-less synthesis reserve. CSV and XLSX execute the same bounded contract.

Next, connect local Ollama only through this parser and build adversarial planner/synthesis evals.
Keep Agent UI/API disabled until those evals pass; keep company KPI selection blocked until an
approved definition is supplied and never enable arbitrary Python/shell execution.

## Acceptance still required on Windows

```text
install Visual Studio Desktop development with C++ + Windows SDK
→ pnpm desktop:dev
→ Hermetic/Tauri native window opens
→ CSV and XLSX upload
→ correct 1508 x 22 profile
→ 52 missing cells / 8 duplicate copies
→ one Analyst run and verified report download
```

`main` must remain untouched until this full path passes.
