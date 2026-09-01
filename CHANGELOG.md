# Changelog

## Unreleased — Canonical pre-release

- Promoted the consolidated single-repository product to protected `main`
- Added Hermetic-derived Next/Tauri UI under `apps/desktop` with licenses/notices preserved
- Added one root launcher for the deterministic backend and unified UI
- Added bounded local Ollama Agent planning with typed allowlisted tools and independent verifier
- Added adversarial fail-closed coverage for prompt injection, tool abuse and unsupported claims
- Added local verifier-passed Agent history without raw-row/prompt/secret retention
- Added fail-closed history list/open/delete UI and deterministic two-manifest comparison
- Added verified Agent Excel/HTML/PDF reports sharing one evidence manifest and SHA-256 binding
- Added Windows Tauri Rust compile and packaged backend executable health smoke in CI
- Kept stable `v1.0.0` blocked pending physical Windows and live local-Ollama acceptance

### Milestone 1 foundation

- Frozen the Hermetic UI/Tauri ↔ LAC deterministic API integration boundary
- Added robust CSV encoding, delimiter, quote, decimal and thousands-separator detection
- Added XLSX/XLSM workbook sheet discovery, deterministic header-row detection and archive guards
- Added visible typed ingestion errors instead of silent malformed-file acceptance
- Added chunked local upload, file-signature validation and multi-sheet selection responses
- Added expanded deterministic profiles with schema, unique counts, date ranges and finding IDs
- Added bounded raw-row-free local Ollama Quick interpretation with citation-presence verification
- Added a Hermetic TypeScript bridge client contract
- Added a Windows double-click launcher with Python alias, Ollama, Docker and backend checks
- Added 1,508 x 22 CSV/XLSX credit-risk regression fixtures and acceptance tests
- Expanded automated suite to 49 tests and 66.29% coverage

## 1.0.0rc1

- Ollama local agent with Fast/Main/Deep model modes
- Persistent local conversations
- Editable personalities and mentor learning profile
- Controlled candidate→approved memory
- Workspace sandbox, audit, optional API token
- Data quality, schema drift, cleaning plans and synthetic test data
- DuckDB dataset SQL
- Broad statistics/ML/forecast/survival/anomaly/drift suite
- General business analytics engine
- Excel Pivot/dashboard, offline HTML dashboard, PDF formatter
- Optional Windows-native Excel PivotTable automation
- NPL DPD/vintage/roll-rate/concentration/NPV/MOIC tools
- Local RAG with FTS5, optional Ollama embeddings and optional OCR
- Read-only database catalog/query connector layer
- Controlled public web research (OFF by default)
- File watcher
- OpenClaw skill/provider examples
- Local project critic and acceptance harness
- Exact-argument human approval queue for workspace writes and external calls
- AST-based SQL guard and sandboxed DuckDB dataset queries
- Remote/cloud model guards, network-bind gate and security headers
- Formula/URL injection-safe Excel exports with non-overwriting output names
- Correct Welch ANOVA routing and portfolio-aware vintage/balance-weighted roll-rate
- Expanded automated suite: 35 tests and 61.83% source coverage
