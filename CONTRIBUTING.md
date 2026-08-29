# Contributing

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[all,dev]"
```

## Required checks

```bash
ruff format --check .
ruff check .
pytest --cov=lacopilot --cov-report=term-missing -q
python -m build
python -m pip check
```

Changes to SQL, file access, agent tools, approvals, web access, spreadsheet exports, statistics or NPL
formulas require regression tests. Do not add arbitrary shell execution or database writes to the LLM
tool surface. Never use real customer/company data in tests or issues.

## Pull requests

- Describe the behavior and risk being changed.
- Add or update tests and documentation.
- Keep company-specific KPI definitions out of generic code unless they are configurable.
- Treat model output as untrusted; deterministic tools remain the calculation boundary.
- Note any Windows/Ollama/Excel/OpenClaw validation that could not be run.
