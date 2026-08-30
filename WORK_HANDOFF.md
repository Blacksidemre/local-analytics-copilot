# Work Handoff

Updated: 2026-08-30
Branch: `hermetic-hybrid-integration`
Baseline: `cfbc2e2` (`main` and branch were identical before hybrid work)
Last validated revision: the current branch HEAD containing this document

## Completed milestone

Milestone 1 backend/bridge slice is implemented. The user chose to continue without rerunning the
final Windows acceptance after the two launcher fixes; this is an explicit acceptance deferral, not
evidence that Windows/Tauri E2E passed.

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
- The Analyst verifier rejects duplicate/unknown findings, invalid numeric values, unbound cards,
  invalid multiple-test correction and invented target/KPI semantics.
- The Hermetic bridge revalidates the Analyst contract before rendering it.
- The hybrid UI now lets the user explicitly select a target and target kind, then displays only
  verifier-passed effect cards and method metadata.
- Local-model explanation and report generation remain deferred; this slice establishes their
  authoritative evidence input first.

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
```

The full coverage run reached the unrelated statistics path and the Linux runner terminated while
loading the native `polars` extension with `Bus error`. This is an environment/native-binary
blocker, not a failing assertion in the changed Milestone 1 paths.

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
- `src/lacopilot/regression_fixture.py`
- `src/lacopilot/app.py`
- `src/lacopilot/tools/common.py`
- `src/lacopilot/tools/data_tools.py`
- `tests/test_ingestion_bridge.py`
- `scripts/launch_windows.ps1`
- `Start_Local_Analytics_Copilot.cmd`
- `integrations/hermetic/lac-bridge-client.ts`

## Known limits / blockers

- The PowerShell launcher behavior is regression-tested statically but must still be run on the
  user's actual Windows 11 machine; `pwsh` is unavailable in this Linux workspace.
- Hermetic upload/Quick UI is wired on `Blacksidemre/hermetic: lac-data-bridge-integration`.
- Hermetic local Investigate remains disabled upstream. Do not remove its provider gate until the
  bounded local planner/verifier design in Milestone 3 is implemented and evaluated.
- Live Qwen interpretation, Docker Desktop and Tauri-on-Windows were not available in this Linux
  workspace.
- The full Python suite currently hits a native `polars` Bus error in this Linux workspace; the
  changed ingestion, Qwen verifier, CSV/XLSX fixture and launcher tests pass independently.
- TestClient emits one upstream Starlette/httpx deprecation warning; tests still pass.

## Next milestone action

Continue Milestone 2 without starting Agent work:

1. Add bounded local-Qwen explanation over Analyst findings only.
2. Verify every numerical sentence against the Analyst finding manifest.
3. Build Analyst dashboard/report output from the same findings, then reopen and validate it.
4. Keep company KPI selection blocked until an approved definition is supplied.

## Acceptance still required on Windows

```text
double click launcher
→ Ollama detected/started
→ Docker detected
→ backend ready
→ Hermetic/Tauri UI opens
→ CSV and XLSX upload
→ correct 1508 x 22 profile
→ 52 missing cells / 8 duplicate copies
→ Qwen interpretation cites supplied facts
→ dashboard cards bind to finding IDs
→ no cloud provider used
```

`main` must remain untouched until this full path passes.
