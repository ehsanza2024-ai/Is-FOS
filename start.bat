@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run install.bat and read docs\INSTALL_CENTRAL_FA.md
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m scripts.run_central %*
if errorlevel 1 pause
