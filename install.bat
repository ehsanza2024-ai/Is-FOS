@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows.ps1"
if errorlevel 1 (
  echo Installation failed. Read the message above. Existing data was not reset.
  pause
  exit /b 1
)
pause
