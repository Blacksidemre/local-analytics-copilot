$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Host "Local Analytics Copilot 1.0 RC1 - Windows installer" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ gerekli." }
python -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11, 3.12 veya 3.13 gerekli." }
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# Installs the full local analytics stack. pyodbc may require Microsoft's ODBC driver for SQL Server.
python -m pip install -e ".[all,dev]"
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
python -m pytest -q
Write-Host "Python ortamı hazır." -ForegroundColor Green

if (Get-Command ollama -ErrorAction SilentlyContinue) {
  Write-Host "Ollama bulundu." -ForegroundColor Green
  Write-Host "RTX 5070 Ti 16 GB için başlangıç modeli: qwen3.5:9b"
  $answer = Read-Host "qwen3.5:9b modelini şimdi indirmek ister misiniz? (E/H)"
  if ($answer -match '^[EeYy]') { ollama pull qwen3.5:9b }
  $deep = Read-Host "Ağır reasoning için gpt-oss:20b modelini de indirmek ister misiniz? (~14 GB) (E/H)"
  if ($deep -match '^[EeYy]') { ollama pull gpt-oss:20b }
} else {
  Write-Host "Ollama bulunamadı. Ollama'nın resmi Windows uygulamasını kurduktan sonra:" -ForegroundColor Yellow
  Write-Host "  ollama pull qwen3.5:9b"
  Write-Host "  ollama pull gpt-oss:20b   # optional deep model"
}

Write-Host "Kurulum sonrası: .\scripts\start_windows.ps1" -ForegroundColor Cyan
