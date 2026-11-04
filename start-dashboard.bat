@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe exit /b 1
rem For read-only service only. Close it before starting the installed central app.
.venv\Scripts\python.exe -m uvicorn app.dashboard:create_app --factory --host 0.0.0.0 --port 8001 --workers 1 --no-proxy-headers --no-access-log
if errorlevel 1 pause
