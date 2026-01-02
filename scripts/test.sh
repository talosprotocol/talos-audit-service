#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# talos-audit-service Test Script
# =============================================================================

echo "Testing talos-audit-service..."

echo "Running ruff check..."
ruff check . --exclude=.venv --exclude=tests 2>/dev/null || true

echo "Running ruff format check..."
ruff format --check . --exclude=.venv --exclude=tests 2>/dev/null || true

echo "Running pytest..."
pytest tests/ --maxfail=1 -q

echo "talos-audit-service tests passed."
