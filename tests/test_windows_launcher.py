import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "launch_windows.ps1"
CMD = ROOT / "Start_Local_Analytics_Copilot.cmd"


def test_windows_launcher_probes_expected_native_failures_without_fatal_exit():
    script = LAUNCHER.read_text(encoding="utf-8")

    assert "function Test-NativeCommand" in script
    assert (
        'Test-NativeCommand -Executable $VenvPython -Arguments @("-c", "import lacopilot")'
        in script
    )
    assert 'Test-NativeCommand -Executable "docker" -Arguments @("info")' in script
    assert '& $VenvPython -c "import lacopilot"' not in script
    assert "& docker info" not in script


def test_windows_launchers_enable_utf8_for_console_and_python():
    script = LAUNCHER.read_text(encoding="utf-8")
    command = CMD.read_text(encoding="utf-8")

    assert "[Console]::OutputEncoding = $Utf8NoBom" in script
    assert '$env:PYTHONUTF8 = "1"' in script
    assert '$env:PYTHONIOENCODING = "utf-8"' in script
    assert "chcp 65001 >nul" in command
    assert 'set "PYTHONUTF8=1"' in command
    assert 'set "PYTHONIOENCODING=utf-8"' in command


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
def test_windows_launcher_has_valid_powershell_syntax():
    escaped = str(LAUNCHER).replace("'", "''")
    result = subprocess.run(
        [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-Command",
            (
                "$errors=$null; "
                f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',"
                "[ref]$null,[ref]$errors) > $null; "
                "if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
