# Canonical Product Plan

## Product goal

One repository and one local application: upload CSV/XLSX, ask in natural language, run deterministic
analytics, verify every numeric finding and download consistent Excel/HTML/PDF reports.

## Milestones

| Milestone | Scope                                                                 | Status  |
| --------- | --------------------------------------------------------------------- | ------- |
| 1         | Deterministic ingestion, profile, Quick Dashboard, local explanation  | PASS    |
| 2         | Analyst statistics, typed findings, verifier and three report formats | PASS    |
| 3         | Local bounded Agent, history, comparison and Agent reports            | PARTIAL |
| 4         | Physical Windows desktop/installer acceptance and stable release      | BLOCKED |

Milestone 3 is functionally implemented and adversarially tested in CI, including local Ollama
planner/synthesis contracts, allowlisted tools, fail-closed verification and local history. It remains
PARTIAL until controlled CSV/XLSX runs pass with a real local model on the target Windows machine.

Milestone 4 requires Visual C++ Build Tools/MSVC/Windows SDK, physical Tauri launch, process
lifecycle checks and clean installer install/upgrade/uninstall. No stable release is allowed before
those checks are evidenced.

Current detailed gates: [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md).
