# RC Handoff — Local Analytics Copilot 1.0 RC1

Bu belge final/stabil ilanı değildir. Kod ve deterministik test kapısı geçmiştir; Windows, GPU,
Ollama, Excel COM, OpenClaw ve canlı bağlantı doğrulamaları hedef bilgisayarda beklemektedir.

## What is delivered
A GitHub-ready local-first Python application with:
- Ollama tool-calling agent
- editable personality / mentor profiles
- broad deterministic statistics & business analytics
- Excel/Pivot/dashboard/PDF/HTML reporting
- NPL analytics and valuation tools
- local RAG + optional OCR/embeddings
- human-approved memory and learning profile
- read-only SQL/database connectors
- optional controlled public-web research
- file watcher automation
- OpenClaw integration skeleton
- local critic + acceptance harness
- audit logs, workspace sandbox and optional API token
- exact-argument approval queue for workspace writes and external calls

## First installation sequence on the target Windows machine

```powershell
# 1. Extract project and open PowerShell in folder
Set-ExecutionPolicy -Scope Process Bypass

# 2. Install Python environment
.\scripts\install_windows.ps1

# 3. Validate local environment
lac doctor
lac privacy-check
lac benchmark-models

# 4. Generate harmless demo data
python scripts/generate_demo_data.py

# 5. Deterministic smoke analysis
lac review incoming/demo_npl.csv --dashboard

# 6. Start UI
.\scripts\start_windows.ps1
```

Open `http://127.0.0.1:8765`.

## Before real employer/company data
- Confirm company/KVKK/information-security policy.
- Keep service on localhost/private network.
- Use a dedicated read-only DB account.
- Put official KPI/data-dictionary/procedure files in `workspace/knowledge`.
- Approve company-specific formulas through the human memory gate.
- Run the demo/acceptance suite first.
- Review pending write/external actions in `/admin`; do not approve unfamiliar arguments.
- Do not enable public web research until privacy boundaries are understood.

## Recommended initial autonomy
Start in “AI prepares / human reviews” mode. Only automate a repeated workflow after its deterministic tools, business rules and outputs have been reviewed multiple times.

## OpenClaw
OpenClaw is optional. Use it to orchestrate/schedule Local Analytics Copilot rather than granting it unrestricted shell/database access. See `OPENCLAW_INTEGRATION.md`.
