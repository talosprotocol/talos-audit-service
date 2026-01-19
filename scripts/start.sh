#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="talos-audit-service"
PID_FILE="/tmp/${SERVICE_NAME}.pid"
PORT="${TALOS_AUDIT_PORT:-8001}"

cd "$REPO_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "$SERVICE_NAME is already running (PID: $(cat "$PID_FILE"))"
    exit 0
fi

echo "Starting $SERVICE_NAME on port $PORT..."
export PYTHONPATH="$(cd ../../sdks/python/src && pwd):$PYTHONPATH"
uvicorn src.adapters.http.main:app --port "$PORT" --host 0.0.0.0 > "/tmp/${SERVICE_NAME}.log" 2>&1 &
echo $! > "$PID_FILE"
sleep 2

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "✓ $SERVICE_NAME started (PID: $(cat "$PID_FILE"), Port: $PORT)"
else
    echo "✗ $SERVICE_NAME failed to start"
    exit 1
fi
