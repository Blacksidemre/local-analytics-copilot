param(
  [ValidateSet("auto", "offline", "live")]
  [string]$AgentMode = "auto",
  [switch]$LiveAgent,
  [string]$Model = "",
  [string]$RunRoot = ""
)

$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
  $PSNativeCommandUseErrorActionPreference = $false
}
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8NoBom
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
  Write-Host "[HATA] Python ortamı bulunamadı. Önce .\scripts\install_windows.ps1 çalıştırın." -ForegroundColor Red
  exit 1
}

if ($LiveAgent) { $AgentMode = "live" }
$Arguments = @("-m", "lacopilot.release_acceptance", "--agent-mode", $AgentMode)
if ($Model) { $Arguments += @("--model", $Model) }
if ($RunRoot) { $Arguments += @("--run-root", $RunRoot) }

Write-Host "[LAC] Release-candidate kabul kontrolleri başlıyor ($AgentMode)..." -ForegroundColor Cyan
& $VenvPython @Arguments
$ExitCode = $LASTEXITCODE

if ($ExitCode -eq 0) {
  Write-Host "[OK] Otomatik kabul kontrolleri tamamlandı." -ForegroundColor Green
} else {
  Write-Host "[HATA] Kabul kontrollerinden biri başarısız oldu." -ForegroundColor Red
}
exit $ExitCode
