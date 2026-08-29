# Build Status — 1.0.0rc1 + Hybrid Milestone 1

Verified on `hermetic-hybrid-integration`, Linux / Python 3.12 on 2026-08-29:

- Ruff formatting: pass
- Ruff lint: pass
- Python compile: pass
- Automated tests: 49 passed
- Measured source coverage: 66.29%
- Package build: pass
- Fresh-wheel install and packaged-resource smoke: pass
- Dependency consistency: pass
- Security/approval/API and deterministic analytics smoke paths: pass
- Deterministic CSV/XLSX Data Bridge regression contract: pass
- Excel archive decompression/entry-count guard: pass
- Controlled 1,508 x 22 credit-risk fixture (52 missing / 8 duplicate copies): pass
- Versioned local bridge upload/profile/Quick API contract: pass

Pending target-machine checks: new double-click launcher on Windows 11, Hermetic fork UI against the
bridge, real `qwen3.5:9b` interpretation, Docker sandbox, Tauri packaging, Excel COM,
PostgreSQL/SQL Server credentials, OCR and OpenClaw. See `docs/HYBRID_ARCHITECTURE.md` and
`docs/PRE_RELEASE_AUDIT.md`.
