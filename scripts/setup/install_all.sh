#!/bin/bash
# WebPForge - Complete Installation Script
# This script sets up a single virtual environment for the entire monorepo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================"
echo "WebPForge - Installation"
echo "============================================"
echo "Project root: $PROJECT_ROOT"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python version: $PYTHON_VERSION"

# Create and activate virtual environment
VENV_DIR="$PROJECT_ROOT/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip and install build tools
echo ""
echo "Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel

# Install packages in dependency order (editable mode)
# Order matters! Packages with no internal deps first, then dependents.

echo ""
echo "============================================"
echo "Installing Python packages"
echo "============================================"

echo ""
echo "[1/4] Installing webp-shared..."
pip install -e "$PROJECT_ROOT/packages/shared"

echo ""
echo "[2/4] Installing webp-converter..."
pip install -e "$PROJECT_ROOT/packages/converter"

echo ""
echo "[3/4] Installing webp-backend..."
pip install -e "$PROJECT_ROOT/apps/backend"

echo ""
echo "[4/4] Installing webp-worker..."
pip install -e "$PROJECT_ROOT/apps/worker"

# Install dev dependencies
echo ""
echo "Installing development dependencies..."
pip install pytest ruff mypy

# Verify installations
echo ""
echo "============================================"
echo "Verifying installations"
echo "============================================"

echo ""
echo "Checking Python package imports..."
python3 -c "
import webp_shared
print('  ✓ webp_shared')
import webp_converter
print('  ✓ webp_converter')
import webp_backend
print('  ✓ webp_backend')
import webp_worker
print('  ✓ webp_worker')
"

# Check for system dependencies
echo ""
echo "Checking system dependencies..."

if command -v cwebp &> /dev/null; then
    CWEBP_VERSION=$(cwebp -version 2>&1 | head -n1)
    echo "  ✓ cwebp installed: $CWEBP_VERSION"
else
    echo "  ⚠ cwebp NOT installed"
    echo "    Install with: sudo apt install webp"
fi

# Frontend setup
echo ""
echo "============================================"
echo "Frontend Setup"
echo "============================================"

FRONTEND_DIR="$PROJECT_ROOT/apps/frontend"

if [ -d "$FRONTEND_DIR" ]; then
    if command -v npm &> /dev/null; then
        echo "Installing frontend dependencies..."
        cd "$FRONTEND_DIR"
        npm install
        echo "  ✓ Frontend dependencies installed"
        cd "$PROJECT_ROOT"
    else
        echo "  ⚠ npm NOT found - skipping frontend installation"
        echo "    Install Node.js to set up the frontend"
    fi
else
    echo "  ⚠ Frontend directory not found at $FRONTEND_DIR"
fi

# Summary
echo ""
echo "============================================"
echo "Installation Complete!"
echo "============================================"
echo ""
echo "Virtual environment: $VENV_DIR"
echo ""
echo "To activate the virtual environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Available commands after activation:"
echo "  webp-backend  - Run the backend server"
echo "  webp-worker   - Run a worker process"
echo ""
echo "Run scripts:"
echo "  ./scripts/run_backend.sh   - Start backend"
echo "  ./scripts/run_worker.sh    - Start worker"
echo "  ./scripts/run_frontend.sh  - Start frontend dev server"
echo ""

# Final dependency check
if ! command -v cwebp &> /dev/null; then
    echo "⚠ IMPORTANT: Install cwebp before running workers:"
    echo "    sudo apt install webp"
    echo ""
fi