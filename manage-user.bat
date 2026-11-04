@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: manage-user.bat LOGIN_NAME viewer
  echo Password is requested interactively, never put it in this command.
  pause
  exit /b 1
)
set "ROLE=%~2"
if "%ROLE%"=="" set "ROLE=viewer"
.venv\Scripts\python.exe -m scripts.manage_user --name "%~1" --role "%ROLE%"
if errorlevel 1 pause
