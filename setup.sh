#!/bin/bash
# Quick setup script for rp-engine

set -e

echo "🚀 RP Engine - Quick Setup"
echo "=========================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3.12 --version 2>&1 | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION"

# Install dependencies system-wide for python3.12
echo "📦 Installing dependencies..."
python3.12 -m pip install --user --break-system-packages pydantic requests python-dotenv pytest mypy ruff --quiet || {
    echo "⚠️  Note: Packages may already be installed"
}

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "   Edit .env if needed (defaults work for local LM Studio)"
else
    echo "✅ .env file exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Start LM Studio: http://localhost:1234/v1"
echo "2. Run the application:"
echo "   python3.12 app/main.py"
echo ""
