#!/bin/bash
# Run the WebPForge backend server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

# Activate virtual environment
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Run ./scripts/setup/install_all.sh first"
    exit 1
fi

# Change to backend directory (so relative paths work)
cd "$PROJECT_ROOT/apps/backend"

echo "Starting WebPForge backend on http://127.0.0.1:5000"
echo "Press Ctrl+C to stop"
echo ""

# Run the backend
python -m webp_backend.app