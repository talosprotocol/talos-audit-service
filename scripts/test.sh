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
pip install -q -r requirements.txt

echo "Running pytest with coverage..."
export PYTHONPATH=$PYTHONPATH:.
pytest --cov=src --cov-report=term-missing --maxfail=1 -q

echo "talos-audit-service tests passed."
