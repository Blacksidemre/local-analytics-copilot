param(
  [int]$Port = 8765,
  [switch]$NoBrowser,
  [switch]$SkipDockerCheck
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
$DesktopRoot = Join-Path $RepoRoot "apps\desktop"
$LogDirectory = Join-Path $RepoRoot "workspace\logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null

function Write-Step([string]$Message) {
  Write-Host "[LAC] $Message" -ForegroundColor Cyan
}

function Test-Http([string]$Url, [int]$TimeoutSeconds = 2) {
  try {
    Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSeconds | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Test-LacBackend([string]$BaseUrl, [int]$TimeoutSeconds = 2) {
  try {
    # /health intentionally exposes only service identity/readiness, so this also works when
    # LAC_API_TOKEN protects every /api route.
    $Response = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec $TimeoutSeconds
    return $Response.data_bridge.status -eq "ready"
  } catch {
    return $false
  }
}

function Test-HybridFrontend([string]$BaseUrl, [int]$TimeoutSeconds = 3) {
  try {
    $Response = Invoke-RestMethod -Uri "$BaseUrl/api/lac/api/v1/health" -TimeoutSec $TimeoutSeconds
    return $Response.data_bridge.status -eq "ready"
  } catch {
    return $false
  }
}

function Find-Pnpm {
  foreach ($Name in @("pnpm.cmd", "pnpm")) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
  }
  return $null
}

function Test-NativeCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @()
  )
  $PreviousErrorActionPreference = $ErrorActionPreference
  try {
    # A probe is allowed to return non-zero. PowerShell 7 can otherwise promote native stderr
    # to a terminating error before the caller can inspect LASTEXITCODE.
    $ErrorActionPreference = "Continue"
    & $Executable @Arguments *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  } finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
  }
}

function Find-CompatiblePython {
  $Candidates = @(
    @{ Exe = "py"; Prefix = @("-3.12") },
    @{ Exe = "py"; Prefix = @("-3.13") },
    @{ Exe = "py"; Prefix = @("-3.11") },
    @{ Exe = "python"; Prefix = @() }
  )
  foreach ($Candidate in $Candidates) {
    if (-not (Get-Command $Candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    $Executable = [string]$Candidate.Exe
    $Arguments = @($Candidate.Prefix) + @(
      "-c",
      "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)"
    )
    if (Test-NativeCommand -Executable $Executable -Arguments $Arguments) { return $Candidate }
  }
  return $null
}

try {
  $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (-not (Test-Path $VenvPython)) {
    Write-Step "İlk kurulum için Python ortamı hazırlanıyor..."
    $Python = Find-CompatiblePython
    if (-not $Python) {
      throw "Python 3.11, 3.12 veya 3.13 bulunamadı. Python 3.12 kurulumunda 'Add python.exe to PATH' seçeneğini açın. Windows 'python' aliası çalışmasa bile py -3.12 desteklenir."
    }
    $PythonExecutable = [string]$Python.Exe
    $Prefix = @($Python.Prefix)
    & $PythonExecutable @Prefix -m venv ".venv"
    if ($LASTEXITCODE -ne 0) { throw "Python sanal ortamı oluşturulamadı." }
  }

  if (-not (Test-NativeCommand -Executable $VenvPython -Arguments @("-c", "import lacopilot"))) {
    Write-Step "Uygulama bağımlılıkları ilk kez kuruluyor..."
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -e ".[all]"
    if ($LASTEXITCODE -ne 0) { throw "Python bağımlılıkları kurulamadı." }
  }

  if (-not (Test-Http "http://127.0.0.1:11434/api/tags")) {
    if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
      throw "Ollama bulunamadı. Ollama'nın resmi Windows uygulamasını bir kez kurup tekrar çift tıklayın."
    }
    Write-Step "Ollama başlatılıyor..."
    Start-Process -FilePath "ollama" -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
    $OllamaReady = $false
    for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
      Start-Sleep -Milliseconds 500
      if (Test-Http "http://127.0.0.1:11434/api/tags") {
        $OllamaReady = $true
        break
      }
    }
    if (-not $OllamaReady) { throw "Ollama başlatıldı ancak sağlık kontrolüne yanıt vermedi." }
  }
  Write-Host "[OK] Ollama hazır" -ForegroundColor Green

  if (-not $SkipDockerCheck) {
    if (Get-Command "docker" -ErrorAction SilentlyContinue) {
      if (Test-NativeCommand -Executable "docker" -Arguments @("info")) {
        Write-Host "[OK] Docker hazır" -ForegroundColor Green
      } else {
        Write-Host "[UYARI] Docker Desktop kapalı. Quick analiz çalışır; sandbox gerektiren hibrit analiz çalışmaz." -ForegroundColor Yellow
      }
    } else {
      Write-Host "[UYARI] Docker bulunamadı. Quick analiz çalışır; sandbox gerektiren hibrit analiz çalışmaz." -ForegroundColor Yellow
    }
  }

  $BackendUrl = "http://127.0.0.1:$Port"
  if (-not (Test-LacBackend $BackendUrl)) {
    Write-Step "Yerel analiz servisi başlatılıyor..."
    $Stdout = Join-Path $LogDirectory "backend.stdout.log"
    $Stderr = Join-Path $LogDirectory "backend.stderr.log"
    Start-Process -FilePath $VenvPython `
      -ArgumentList @("-m", "uvicorn", "lacopilot.app:app", "--host", "127.0.0.1", "--port", "$Port") `
      -WorkingDirectory $RepoRoot `
      -WindowStyle Hidden `
      -RedirectStandardOutput $Stdout `
      -RedirectStandardError $Stderr | Out-Null
    $BackendReady = $false
    for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
      Start-Sleep -Milliseconds 500
      if (Test-LacBackend $BackendUrl) {
        $BackendReady = $true
        break
      }
    }
    if (-not $BackendReady) {
      throw "Analiz servisi başlatılamadı. Ayrıntı: workspace\logs\backend.stderr.log"
    }
  }
  Write-Host "[OK] Local Analytics Copilot hazır: $BackendUrl" -ForegroundColor Green

  $AppUrl = $BackendUrl
  if (Test-Path (Join-Path $DesktopRoot "package.json")) {
    $Pnpm = Find-Pnpm
    if (-not $Pnpm) {
      throw "Masaüstü arayüzü için pnpm bulunamadı. Node.js ve Corepack/pnpm kurulumunu tamamlayın."
    }
    if (-not (Test-Path (Join-Path $DesktopRoot "node_modules"))) {
      Write-Step "Masaüstü arayüzü bağımlılıkları ilk kez hazırlanıyor..."
      & $Pnpm --dir $DesktopRoot install --frozen-lockfile
      if ($LASTEXITCODE -ne 0) {
        throw "Masaüstü arayüzü bağımlılıkları kurulamadı. İnternet bağlantısını kontrol edip yeniden deneyin."
      }
    }

    $FrontendUrl = "http://127.0.0.1:3000"
    $env:NEXT_PUBLIC_LAC_HYBRID = "1"
    $env:LAC_BRIDGE_URL = $BackendUrl
    $env:HERMETIC_HOST = "127.0.0.1"
    if (-not (Test-HybridFrontend $FrontendUrl)) {
      Write-Step "Tek uygulama arayüzü başlatılıyor..."
      $FrontendStdout = Join-Path $LogDirectory "frontend.stdout.log"
      $FrontendStderr = Join-Path $LogDirectory "frontend.stderr.log"
      Start-Process -FilePath $Pnpm `
        -ArgumentList @("dev") `
        -WorkingDirectory $DesktopRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendStdout `
        -RedirectStandardError $FrontendStderr | Out-Null
      $FrontendReady = $false
      for ($Attempt = 0; $Attempt -lt 120; $Attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-HybridFrontend $FrontendUrl) {
          $FrontendReady = $true
          break
        }
      }
      if (-not $FrontendReady) {
        throw "Tek uygulama arayüzü başlatılamadı. Ayrıntı: workspace\logs\frontend.stderr.log"
      }
    }
    $AppUrl = $FrontendUrl
    Write-Host "[OK] Tek Local Analytics Copilot arayüzü hazır: $AppUrl" -ForegroundColor Green
  }

  if (-not $NoBrowser) { Start-Process $AppUrl }
  Write-Host "Bu pencereyi kapatabilirsiniz; uygulama yerel olarak çalışmaya devam eder." -ForegroundColor DarkGray
} catch {
  Write-Host "[HATA] $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
