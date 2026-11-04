#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'First run ./install.sh and read docs/INSTALL_CENTRAL_FA.md'
  exit 1
fi
exec .venv/bin/python -m scripts.run_central "$@"
