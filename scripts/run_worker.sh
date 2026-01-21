#!/bin/bash
# Run a WebPForge worker

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

# Check for cwebp
if ! command -v cwebp &> /dev/null; then
    echo "Error: cwebp is not installed"
    echo "Install with: sudo apt install webp"
    exit 1
fi

echo "Starting WebPForge worker..."
echo "Backend: 127.0.0.1:5055 (TCP), 127.0.0.1:5056 (UDP)"
echo "Press Ctrl+C to stop"
echo ""

# Run the worker with verbose logging
webp-worker --verbose "$@"