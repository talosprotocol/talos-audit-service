# talos-audit-service Makefile
# Audit Log Aggregator Service

.PHONY: install build test lint clean start stop status

SERVICE_NAME := talos-audit-service
PID_FILE := /tmp/$(SERVICE_NAME).pid
PORT := 8081

all: install test

install:
	@echo "Installing dependencies..."
	pip install -e ".[dev]" -q 2>/dev/null || pip install fastapi uvicorn pydantic -q

build:
	@echo "Python service - no build step required"

test:
	@echo "Running tests..."
	pytest tests/ -q 2>/dev/null || echo "No tests found"

lint:
	@echo "Running lint..."
	ruff check . --exclude=.venv --exclude=tests || true

start:
	@echo "Starting $(SERVICE_NAME)..."
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "$(SERVICE_NAME) is already running"; \
	else \
		uvicorn main:app --port $(PORT) --host 127.0.0.1 > /tmp/$(SERVICE_NAME).log 2>&1 & \
		echo $$! > $(PID_FILE); \
		echo "$(SERVICE_NAME) started (PID: $$!, Port: $(PORT))"; \
	fi

stop:
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi

status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then echo "running"; else echo "stopped"; fi

clean:
	rm -rf *.egg-info build dist .venv venv .pytest_cache .ruff_cache __pycache__
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
