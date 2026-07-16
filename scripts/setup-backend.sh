#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../backend"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
if [ "${1:-}" = "--dev" ]; then
  .venv/bin/python -m pip install -r requirements-dev.txt
fi
echo "Backend environment created at backend/.venv"
