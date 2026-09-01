# Build Status — Canonical Pre-release

The canonical product lives entirely in `Blacksidemre/local-analytics-copilot`. `main` is protected
and receives reviewed integration changes through pull requests; the old Hermetic fork is not a
runtime or build dependency.

## Automated gates

- Linux Python 3.11/3.12 regression and coverage: required
- Windows Python smoke/privacy: required
- Ruff format/lint, wheel build and dependency consistency: required
- Desktop TypeScript, Vitest, ESLint, Prettier and production Next build: required
- Windows Tauri `cargo check --locked`: required
- Packaged PyInstaller backend executable `/health` smoke: required
- CSV/XLSX parity, Agent adversarial/verifier/report/history contracts: required

Milestone 1 (Quick) and Milestone 2 (Analyst) are PASS. Milestone 3 remains PARTIAL until controlled
CSV/XLSX Agent tests use a real local Ollama model on the target Windows PC.

## Physical gate

Repository-side compile and executable smoke tests do not prove an installed desktop application.
Stable `v1.0.0` remains blocked until the target Windows machine completes Tauri launch, model,
report, lifecycle, installer, upgrade and uninstall acceptance. See
[`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).
