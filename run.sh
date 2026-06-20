#!/bin/bash
# Run RP Engine with .venv

cd /home/pablo/projects/rp-engine

# Make sure .venv exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running setup..."
    bash setup.sh
fi

# Run app with .venv
echo ""
echo "🚀 Starting RP Engine..."
echo ""
.venv/bin/python app/main.py
