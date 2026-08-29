$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Host "Local Analytics Copilot - Windows kurulumu" -ForegroundColor Cyan

function Find-CompatiblePython {
  $Candidates = @(
    @{ Exe = "py"; Prefix = @("-3.12") },
    @{ Exe = "py"; Prefix = @("-3.13") },
    @{ Exe = "py"; Prefix = @("-3.11") },
    @{ Exe = "python"; Prefix = @() }
  )
  foreach ($Candidate in $Candidates) {
    if (-not (Get-Command $Candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    try {
      $Executable = [string]$Candidate.Exe
      $Prefix = @($Candidate.Prefix)
      & $Executable @Prefix -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)"
      if ($LASTEXITCODE -eq 0) { return $Candidate }
    } catch { }
  }
  return $null
}

$Python = Find-CompatiblePython
if (-not $Python) {
  throw "Python 3.11, 3.12 veya 3.13 bulunamadı. Önerilen sürüm Python 3.12'dir. 'python' Windows aliası çalışmasa bile py -3.12 otomatik denenir."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  $PythonExecutable = [string]$Python.Exe
  $Prefix = @($Python.Prefix)
  & $PythonExecutable @Prefix -m venv ".venv"
  if ($LASTEXITCODE -ne 0) { throw "Python sanal ortamı oluşturulamadı." }
}
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e ".[all,dev]"
if ($LASTEXITCODE -ne 0) { throw "Python bağımlılıkları kurulamadı." }

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

& $VenvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Kurulum testi başarısız oldu." }
Write-Host "Python ortamı ve Data Bridge testleri hazır." -ForegroundColor Green

if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
  Write-Host "Ollama bulundu." -ForegroundColor Green
  Write-Host "Önerilen başlangıç modeli: qwen3.5:9b"
  $Answer = Read-Host "qwen3.5:9b modelini şimdi indirmek ister misiniz? (E/H)"
  if ($Answer -match '^[EeYy]') { ollama pull qwen3.5:9b }
  $Deep = Read-Host "Opsiyonel gpt-oss:20b modelini de indirmek ister misiniz? (E/H)"
  if ($Deep -match '^[EeYy]') { ollama pull gpt-oss:20b }
} else {
  Write-Host "Ollama bulunamadı. Resmi Windows uygulamasını kurduktan sonra başlangıç dosyasını yeniden açın." -ForegroundColor Yellow
}

Write-Host "Kurulum tamamlandı. Bundan sonra Start_Local_Analytics_Copilot.cmd dosyasına çift tıklayın." -ForegroundColor Cyan
