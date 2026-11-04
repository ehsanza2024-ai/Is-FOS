@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First install: py -3 -m venv .venv
  echo Then: .venv\Scripts\python -m pip install -r requirements.lock.txt
  pause
  exit /b 1
)
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
