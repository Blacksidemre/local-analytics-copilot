# Work Handoff

Updated: 2026-08-30
Branch: `hermetic-hybrid-integration`
Baseline: `cfbc2e2` (`main` and branch were identical before hybrid work)
Last validated revision: the current branch HEAD containing this document

## Completed milestone

Milestone 1 backend/bridge slice is implemented:

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
  citation-presence verification separately from analytical validation.
- Windows double-click launcher supports `py -3.12` when the `python` alias is broken.
- Hermetic adapter client and integration sequence live under `integrations/hermetic/`.

## Validation

```text
ruff format --check .                 PASS
ruff check .                          PASS
python -m compileall -q src scripts   PASS
pytest --cov=lacopilot -q             51 passed, 66.64%
node --check lac-bridge-client.ts     PASS
bridge client runtime smoke           PASS
git diff --check                      PASS
```

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

- The new PowerShell launcher was statically reviewed but must still be run on the user's actual
  Windows 11 machine; Linux CI cannot prove Docker Desktop/Ollama process startup behavior.
- Hermetic UI source is intentionally not copied into this repo. Create/use the planned
  `Blacksidemre/hermetic` fork and wire its upload/Quick flow through the bridge client.
- Hermetic local Investigate remains disabled upstream. Do not remove its provider gate until the
  bounded local planner/verifier design in Milestone 3 is implemented and evaluated.
- Live Qwen interpretation and Docker sandbox were not available in this Linux workspace.
- TestClient emits one upstream Starlette/httpx deprecation warning; tests still pass.

## Next milestone action

Finish Milestone 1 end-to-end UI integration before starting Analyst/Agent work:

1. Fork/pin Hermetic at the inspected upstream revision.
2. Replace its hybrid-mode upload/profile source with `LacBridgeClient`.
3. Bind KPI cards to stable finding IDs and show typed ingestion errors in the UI.
4. Package LAC as the Tauri Python sidecar using Hermetic's existing desktop build pattern.
5. Run the real Windows acceptance path with both regression files and `qwen3.5:9b`.
6. Only after that passes, begin Milestone 2 Analyst Pipeline.

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
