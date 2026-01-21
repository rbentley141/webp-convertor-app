#!/bin/bash
# Run the WebPForge frontend development server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/apps/frontend"

cd "$FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Starting WebPForge frontend on http://localhost:5173"
echo "API requests will be proxied to http://127.0.0.1:5000"
echo "Press Ctrl+C to stop"
echo ""

npm run dev