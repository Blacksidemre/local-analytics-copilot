# Risk Register — Release 1.0 RC1

| ID | Risk | Severity | 1.0 control | Residual action |
|---|---|---:|---|---|
| R1 | LLM invents calculations | High | deterministic tools + bounded tool outputs | acceptance/eval on real schemas |
| R2 | Confidential data leaves PC | Critical | web OFF default, local Ollama, PII-ish query guard | company DLP/policy + user discipline |
| R3 | Agent edits production DB | Critical | no write DB tool, read-only SQL guard | **technically read-only DB account** |
| R4 | Agent accesses whole PC | High | workspace sandbox, no arbitrary shell tool | OS/container isolation for future tools |
| R5 | Wrong statistical method | High | method router, assumptions, effect-size/guardrails | analyst review + domain test cases |
| R6 | Wrong company KPI/recovery definition | High | candidate→human-approved memory + local RAG | ingest official data dictionary/procedure |
| R7 | Runaway agent loop/context | Medium | max tool rounds, context, output/result caps | benchmark/monitor logs |
| R8 | Large Excel exhausts RAM | Medium | DuckDB path for dataset SQL, row caps | Polars/DuckDB-specific streaming workflows |
| R9 | Prompt injection in documents | High | untrusted-content prompt rule, narrow tool surface, exact-argument approval, no arbitrary shell | adversarial RAG evals + document trust labels |
| R10 | Plugin/supply-chain risk | High | OpenClaw optional; upper bounds, CI and Dependabot | lock reviewed releases; review every plugin/update |
| R11 | Self-improvement corrupts rules | High | agent can only propose candidate memory | human approval + regression tests |
| R12 | Significance mistaken for importance | Medium | effect sizes, CI, business guardrails | approved practical thresholds |
| R13 | Anomaly mistaken for fraud | High | explicit “review candidate” language | investigation workflow/human evidence |
| R14 | Remote UI exposed publicly | Critical | loopback default; non-loopback requires explicit flag + API token | private VPN/firewall; no public port forwarding |
| R19 | Generated spreadsheet executes attacker-controlled formulas/links | High | XlsxWriter formula/URL conversion disabled | open unknown exports in Protected View; regression tests |
| R20 | OpenClaw provider/version drift | High | integration optional and marked experimental | pin/test exact version before use |
| R15 | API token leakage | High | environment config; browser local storage only if used | rotate token; do not put in prompts/logs |
| R16 | Synthetic data leaks rare records | High | identifier replacement + privacy warning | disclosure-risk tests / DP if required |
| R17 | ML leakage/overfitting | High | CV baseline + warning | temporal split/calibration/leakage review |
| R18 | Deep model exceeds VRAM | Medium | main fallback + conservative context | benchmark and reduce context/model size |
