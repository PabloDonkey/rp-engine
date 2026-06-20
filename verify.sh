#!/bin/bash
# Verify rp-engine setup

echo "🔍 RP Engine - Setup Verification"
echo "=================================="
echo ""

ERRORS=0

# Check Python version
echo "Checking Python 3.12..."
if python3.12 --version &> /dev/null; then
    PYTHON_VERSION=$(python3.12 --version 2>&1 | cut -d' ' -f2)
    echo "✅ Python $PYTHON_VERSION"
else
    echo "❌ Python 3.12 not found"
    ERRORS=$((ERRORS + 1))
fi

# Check virtual environment
echo ""
echo "Checking virtual environment..."
if [ -d ".venv/bin" ]; then
    echo "✅ Virtual environment exists"
    
    if [ -f ".venv/bin/python" ]; then
        echo "✅ Python wrapper available"
    else
        echo "❌ Python wrapper not found"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "❌ Virtual environment not found"
    echo "   Run: bash setup.sh"
    ERRORS=$((ERRORS + 1))
fi

# Check packages in system Python (since .venv is a wrapper)
echo ""
echo "Checking Python packages..."
for package in pydantic requests dotenv pytest; do
    if python3.12 -c "import ${package}" 2>/dev/null; then
        echo "✅ ${package}"
    else
        echo "⚠️  ${package} not installed"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check .env file
if [ -f ".env" ]; then
    echo "✅ .env file exists"
else
    echo "⚠️  .env file not found"
    ERRORS=$((ERRORS + 1))
fi

# Check project files
echo ""
echo "Checking project structure..."

FILES=(
    "app/main.py"
    "app/config.py"
    "llm/client.py"
    "memory/session.py"
    "memory/character.py"
    "memory/world.py"
    "memory/store.py"
    "engine/orchestrator.py"
    "engine/prompt_builder.py"
    "tests/test_models.py"
    "pyproject.toml"
    ".github/workflows/ci.yml"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (missing)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check data directories
echo ""
echo "Checking data directories..."
for dir in "data/sessions" "data/worlds" "data/characters"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir"
    else
        echo "❌ $dir (missing)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Summary
echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed! Ready to run:"
    echo ""
    echo "Option 1 - Activate venv and run:"
    echo "   source .venv/bin/activate"
    echo "   python app/main.py"
    echo ""
    echo "Option 2 - Run directly:"
    echo "   .venv/bin/python app/main.py"
    echo ""
    echo "Make sure LM Studio is running on http://localhost:1234/v1"
else
    echo "❌ $ERRORS check(s) failed"
    echo ""
    echo "Run setup.sh to fix:"
    echo "   bash setup.sh"
fi
echo ""
