$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
  throw "Önce .\scripts\install_windows.ps1 çalıştırın."
}
& .\.venv\Scripts\Activate.ps1
lac doctor
Write-Host "UI: http://127.0.0.1:8765" -ForegroundColor Cyan
lac serve --host 127.0.0.1 --port 8765
