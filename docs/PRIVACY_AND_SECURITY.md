# Privacy & Security Model

## Default trust boundary
`workspace/` is the agent's data area. File tools reject paths that escape it.

Recommended directories:
- `workspace/incoming` — source files
- `workspace/knowledge` — approved company/orientation documents
- `workspace/outputs` — generated reports
- `workspace/logs` — audit JSONL
- `workspace/archive` — completed inputs

## Database safety
Application-side SQL validation parses one `SELECT`/`WITH` query and rejects DML, DDL, multiple
statements and locking/output constructs. Dataset SQL can reference only the in-memory `data` table;
DuckDB external access and unsigned extensions are disabled.

**Primary security control:** connect with a database account that is technically read-only. Application text filtering is defense-in-depth, not a replacement for database permissions.

## Web safety
`LAC_ALLOW_WEB=false` by default.
If enabled, public search rejects obvious email/phone/TR-ID-like strings and long raw-looking queries. This cannot automatically identify every form of confidential information. Do not place customer/debtor rows, internal secrets or non-public company data in web queries.

External calls and workspace writes are queued by default. A human must inspect and approve the exact
tool name and arguments in `/admin` or with `lac action-approve`. Approval does not authorize a changed
or future call.

## Model endpoint safety

Loopback and private-LAN Ollama endpoints are accepted by default. Public/remote endpoints and
`:cloud` model tags are blocked unless explicitly enabled. A private-LAN host still crosses the local
process boundary; review firewall, TLS and company policy before using it.

## Memory safety
The LLM may create a **candidate** memory/rule. It cannot approve the candidate through its tool surface. A human must approve it via UI/API/CLI.

## Analytics safety
- Outlier/anomaly != fraud/error.
- Correlation/regression association != causation.
- Company-specific KPI/recovery formulas require approved definitions.
- Synthetic data generator is for testing and gives no formal privacy guarantee.
- Financial scenario outputs are assumptions, not automatic bid recommendations.

Run `lac privacy-check` before using real data.

See `SECURITY.md` for supported-version and vulnerability-reporting guidance.
