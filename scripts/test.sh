#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# talos-audit-service Test Script
# =============================================================================

echo "Testing talos-audit-service..."

echo "Running ruff check..."
ruff check .

echo "Running ruff format check..."
ruff format --check .

echo "Installing dependencies..."
if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi
PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 .venv/bin/python -m pip install -q -r requirements.txt pytest-cov pytest-asyncio -e ../../contracts/python -e ../../libs/talos-config -e ../../sdks/python

echo "Running pytest with coverage..."
export PYTHONPATH=${PYTHONPATH:-}:.
.venv/bin/python -m pytest --cov=src --cov-report=term-missing --maxfail=1 -q

echo "talos-audit-service tests passed."
