---
name: local-analytics-copilot
summary: Use Local Analytics Copilot for secure local data profiling, statistics, BI/Excel, SQL and NPL analytics.
---

# Local Analytics Copilot skill

Use the Local Analytics Copilot API for deterministic calculations rather than asking the LLM to invent results.

## Operating rules
1. Keep local/company data local. Public web search must never contain raw confidential rows or identifiers.
2. Profile unfamiliar data before advanced analysis.
3. Prefer the high-level analytics, BI and NPL engines over ad-hoc calculations.
4. Database access is read-only and must also use a genuinely read-only DB service account.
5. Outliers/anomalies are review candidates, not proof of fraud/error.
6. Company-specific formulas require approved local memory/knowledge evidence.
7. Candidate business rules require human approval before becoming trusted memory.
8. Explain method choice, assumptions, uncertainty and business meaning when Mentor mode is active.
9. Do not execute irreversible file/database actions without an explicit approved workflow.

## Service
Default service: `http://127.0.0.1:8765`
OpenAPI: `http://127.0.0.1:8765/openapi.json`

Recommended integration: register the local FastAPI/OpenAPI surface in OpenClaw with a narrow allowlist. Keep Local Analytics Copilot independent from OpenClaw so deterministic analytics continues to work even if the agent framework changes.
