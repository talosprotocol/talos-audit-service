# talos-audit-service Makefile
# Audit Log Aggregator Service

.PHONY: install build test lint clean start stop status docker-build typecheck

SERVICE_NAME := talos-audit-service
PID_FILE := /tmp/$(SERVICE_NAME).pid
PORT := 8081

all: install test

install:
	@echo "Installing dependencies..."
	pip install -e ".[dev]"

build:
	@echo "Python service - no build step required"

docker-build:
	@echo "Building Docker image..."
	docker build -t $(SERVICE_NAME):latest .

test:
	@echo "Running tests..."
	pytest --cov=src --cov-report=term-missing

lint:
	@echo "Running lint..."
	ruff check .
	ruff format --check .

start:
	@echo "Starting $(SERVICE_NAME)..."
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "$(SERVICE_NAME) is already running"; \
	else \
		uvicorn src.main:app --port 8000 --host 127.0.0.1 > /tmp/$(SERVICE_NAME).log 2>&1 & \
		echo $$! > $(PID_FILE); \
		echo "$(SERVICE_NAME) started (PID: $$!, Port: 8000)"; \
	fi

stop:
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi

status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then echo "running"; else echo "stopped"; fi

clean:
	rm -rf *.egg-info build dist .venv venv .pytest_cache .ruff_cache __pycache__
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

typecheck:
	@echo "Typecheck not implemented for $(SERVICE_NAME)"
