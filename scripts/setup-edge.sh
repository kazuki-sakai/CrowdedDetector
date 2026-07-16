#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../edge"
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
echo "Edge environment created at edge/.venv"
