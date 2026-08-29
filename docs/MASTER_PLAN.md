# Master Plan — Release 1.0 RC1 Status

## Product goal
A local-first AI colleague that can **teach**, **analyze**, **calculate with deterministic tools**, **produce BI/Excel outputs**, specialize in **NPL/asset-management analytics**, and improve through **approved memory and reusable workflows**.

## Phase status

| Phase | Scope | 1.0 status |
|---|---|---|
| 0 | Governance, risk, cost, benchmark | Implemented |
| 1 | Ollama agent core, UI/CLI, sandbox, audit | Implemented |
| 2 | Broad analytics/statistics engine | Implemented baseline |
| 3 | BI/Excel/Pivot/HTML/PDF | Implemented baseline |
| 4 | NPL intelligence | Implemented baseline |
| 5 | Local RAG + Mentor + personality | Implemented |
| 6 | Approved memory + workflow pattern learning | Implemented |
| 7 | PostgreSQL/SQL Server read-only connector layer | Implemented baseline |
| 8 | Controlled public web research | Implemented, default OFF |
| 9 | File watcher / remote deployment guidance | Implemented baseline |
| 10 | Local critic + acceptance harness | Implemented |

## What “baseline” means
The feature is operational and testable, but company-specific production hardening still requires real schema/formula definitions, permissions, performance benchmarking and acceptance data from the target environment.

## Release gates before real company use
1. Run `ruff format --check .`, `ruff check .` and `pytest --cov=lacopilot -q`.
2. Run `lac doctor`.
3. Run `lac privacy-check`.
4. Run model benchmark on the actual RTX 5070 Ti workstation.
5. Run acceptance prompts using a demo dataset with the same schema shape as real data.
6. Configure a technically read-only DB account.
7. Approve company KPI/Recovery definitions in local memory/knowledge.
8. Review company policy before moving or remotely accessing real data.
9. Run `lac project-review --mode deep` and examine HIGH/BLOCKER items.
10. Only then promote individual workflows from “assistant prepares” to greater autonomy.

## Post-RC optional expansions
- Native Excel COM PivotTable/Slicer automation for Windows-only workflows
- Power BI/Power Query connectors
- Dedicated change-point libraries and richer causal inference modules
- Model calibration/fairness dashboard for production ML
- Container/Windows Sandbox isolation for higher-risk tools
- Organization SSO/authentication if deployed beyond single-user private use
