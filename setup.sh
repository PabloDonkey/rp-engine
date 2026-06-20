#!/bin/bash
# Setup script for rp-engine with .venv

set -e

echo "🚀 RP Engine - Setup"
echo "===================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3.12 --version 2>&1 | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION"

# Create virtual environment wrapper using system Python
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python wrapper in .venv..."
    mkdir -p .venv/bin
    
    # Create wrapper scripts
    cat > .venv/bin/python << 'WRAPPER'
#!/bin/bash
exec python3.12 "$@"
WRAPPER
    chmod +x .venv/bin/python
    
    cat > .venv/bin/python3.12 << 'WRAPPER'
#!/bin/bash
exec python3.12 "$@"
WRAPPER
    chmod +x .venv/bin/python3.12
    
    cat > .venv/bin/pip << 'WRAPPER'
#!/bin/bash
exec python3.12 -m pip "$@"
WRAPPER
    chmod +x .venv/bin/pip
    
    echo "✅ Python wrapper created"
else
    echo "✅ Python wrapper exists"
fi

# Install dependencies using system Python
echo "📦 Installing dependencies..."
python3.12 -m pip install --user --break-system-packages pydantic requests python-dotenv pytest mypy ruff --quiet 2>/dev/null || \
python3.12 -m pip install pydantic requests python-dotenv pytest mypy ruff --quiet

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
else
    echo "✅ .env file exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the application:"
echo "   source .venv/bin/python app/main.py"
echo ""
echo "Or:"
echo "   .venv/bin/python app/main.py"
echo ""
echo "Or:"
echo "   python3.12 app/main.py"
echo ""
echo "Make sure LM Studio is running on http://localhost:1234/v1"
echo ""
