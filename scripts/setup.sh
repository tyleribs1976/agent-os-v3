#!/usr/bin/env bash
#
# Agent-OS v3 Setup Script
# Creates virtual environment and installs dependencies
#

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# Check if we're in the right directory
if [[ ! -f "src/orchestrator.py" ]] || [[ ! -f "requirements.txt" ]]; then
    error "Must be run from /opt/agent-os-v3 directory"
    exit 1
fi

info "Starting Agent-OS v3 setup..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
info "Found Python $PYTHON_VERSION"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
    error "Python 3.8 or higher is required"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [[ ! -d "venv" ]]; then
    info "Creating virtual environment..."
    python3 -m venv venv
    info "Virtual environment created at ./venv"
else
    warn "Virtual environment already exists at ./venv"
fi

# Activate virtual environment
info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
info "Upgrading pip..."
pip install --upgrade pip --quiet

# Install requirements
if [[ -f "requirements.txt" ]]; then
    info "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    info "Dependencies installed successfully"
else
    error "requirements.txt not found"
    exit 1
fi

# Verify critical imports
info "Verifying critical dependencies..."
python3 -c "import psycopg2; import requests; import dotenv" 2>/dev/null
if [[ $? -eq 0 ]]; then
    info "Critical dependencies verified"
else
    error "Failed to import critical dependencies"
    exit 1
fi

# Check for .env file
if [[ ! -f ".env" ]]; then
    warn ".env file not found - you may need to create one"
    warn "See .env.example if available"
else
    info "Found .env file"
fi

info "Setup complete!"
info ""
info "To activate the virtual environment, run:"
info "  source venv/bin/activate"
info ""
info "To run the orchestrator:"
info "  python3 src/orchestrator.py"
