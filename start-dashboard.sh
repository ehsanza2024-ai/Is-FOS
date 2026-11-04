#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
# Read-only service only. Close it before running the installed central application.
exec .venv/bin/python -m uvicorn app.dashboard:create_app --factory --host "${MAZANDASHT_DASHBOARD_HOST:-0.0.0.0}" --port 8001 --workers 1 --no-proxy-headers --no-access-log "$@"
