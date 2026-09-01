@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_windows.ps1"
if errorlevel 1 (
  echo.
  echo Local Analytics Copilot baslatilamadi. Yukaridaki mesaji kontrol edin.
  pause
)
endlocal
