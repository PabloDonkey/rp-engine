#!/bin/bash
# Start the RP Engine REST API server

set -e

# Get the project directory (directory where this script is located)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting RP Engine API..."
echo "========================"
echo ""

# Check if .venv/bin/python exists
if [ ! -f "$PROJECT_DIR/.venv/bin/python" ]; then
    echo "❌ Error: .venv/bin/python not found"
    echo "   Run ./setup.sh first to initialize the environment"
    exit 1
fi

# Check if Flask and flask-cors are installed
if ! "$PROJECT_DIR/.venv/bin/python" -c "import flask" 2>/dev/null; then
    echo "Installing Flask..."
    "$PROJECT_DIR/.venv/bin/python" -m pip install --user flask flask-cors --break-system-packages -q
elif ! "$PROJECT_DIR/.venv/bin/python" -c "import flask_cors" 2>/dev/null; then
    echo "Installing flask-cors..."
    "$PROJECT_DIR/.venv/bin/python" -m pip install --user flask-cors --break-system-packages -q
fi

cd "$PROJECT_DIR"

echo "✅ Environment ready"
echo ""
echo "Starting API server..."
echo "API URL: http://localhost:5000"
echo "Web UI: http://localhost:5000"
echo "LM Studio: http://localhost:1234/v1"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the API
"$PROJECT_DIR/.venv/bin/python" -m app.api
