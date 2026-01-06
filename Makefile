# Agent-OS v3 Makefile
# Provides common development and maintenance tasks

.PHONY: help install run test lint clean

# Default target
help:
	@echo "Agent-OS v3 Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make install    - Install Python dependencies"
	@echo "  make run        - Run the orchestrator"
	@echo "  make test       - Run tests (placeholder - no tests directory yet)"
	@echo "  make lint       - Run code quality checks (pylint/flake8)"
	@echo "  make clean      - Clean Python cache files and logs"
	@echo ""

# Install dependencies from requirements.txt
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Dependencies installed successfully"

# Run the orchestrator
run:
	@echo "Starting Agent-OS v3 orchestrator..."
	@cd /opt/agent-os-v3 && python3 src/orchestrator.py

# Run tests (placeholder since no tests directory exists yet)
test:
	@if [ -d "tests" ]; then \
		echo "Running tests..."; \
		python3 -m pytest tests/ -v; \
	else \
		echo "No tests directory found. Create tests/ directory and add test files."; \
		exit 1; \
	fi

# Run linting and code quality checks
lint:
	@echo "Running code quality checks..."
	@if command -v pylint >/dev/null 2>&1; then \
		echo "Running pylint..."; \
		pylint src/ scripts/ --disable=C0114,C0115,C0116 || true; \
	else \
		echo "pylint not installed. Install with: pip install pylint"; \
	fi
	@if command -v flake8 >/dev/null 2>&1; then \
		echo "Running flake8..."; \
		flake8 src/ scripts/ --max-line-length=100 --ignore=E501,W503 || true; \
	else \
		echo "flake8 not installed. Install with: pip install flake8"; \
	fi

# Clean up cache files and logs
clean:
	@echo "Cleaning up cache files and logs..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@if [ -d "logs" ]; then \
		echo "Truncating log files..."; \
		find logs/ -type f -name "*.log" -exec truncate -s 0 {} \; 2>/dev/null || true; \
	fi
	@echo "Cleanup complete"
