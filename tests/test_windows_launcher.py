import base64
import codecs
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "launch_windows.ps1"
CMD = ROOT / "Start_Local_Analytics_Copilot.cmd"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")


def test_windows_launcher_probes_expected_native_failures_without_fatal_exit():
    script = LAUNCHER.read_text(encoding="utf-8-sig")

    assert "function Test-NativeCommand" in script
    assert (
        'Test-NativeCommand -Executable $VenvPython -Arguments @("-c", "import lacopilot")'
        in script
    )
    assert 'Test-NativeCommand -Executable "docker" -Arguments @("info")' in script
    assert '& $VenvPython -c "import lacopilot"' not in script
    assert "& docker info" not in script


def test_windows_launchers_enable_utf8_for_console_and_python():
    raw_script = LAUNCHER.read_bytes()
    assert raw_script.startswith(codecs.BOM_UTF8)
    script = raw_script.decode("utf-8-sig")
    command = CMD.read_text(encoding="utf-8")

    assert "[Console]::OutputEncoding = $Utf8NoBom" in script
    assert '$env:PYTHONUTF8 = "1"' in script
    assert '$env:PYTHONIOENCODING = "utf-8"' in script
    assert "chcp 65001 >nul" in command
    assert 'set "PYTHONUTF8=1"' in command
    assert 'set "PYTHONIOENCODING=utf-8"' in command
    assert "Ollama hazır" in script
    assert "Docker Desktop kapalı" in script
    assert "Quick analiz çalışır" in script
    assert "function Test-HybridFrontend" in script
    assert 'Join-Path $RepoRoot "apps\\desktop"' in script
    assert '$env:NEXT_PUBLIC_LAC_HYBRID = "1"' in script
    assert "$env:LAC_BRIDGE_URL = $BackendUrl" in script
    assert "Start-Process -FilePath $Pnpm" in script
    assert "if (-not $NoBrowser) { Start-Process $AppUrl }" in script
    assert "hazÄ±r" not in script
    assert "kapalÄ±" not in script
    assert "Ã§alÄ±ÅŸÄ±r" not in script


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is not installed")
def test_windows_powershell_parses_utf8_source_and_syntax():
    escaped = str(LAUNCHER).replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',"
        "[ref]$tokens,[ref]$errors) > $null; "
        "if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }"
    )
    encoded_command = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded_command,
        ],
        check=False,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
