#!/usr/bin/env python3.12
"""Test that the application imports correctly."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.main import main
    from app.config import config
    from engine.orchestrator import Orchestrator
    from llm.client import LMStudioClient
    from memory.session import SessionMemory
    print("✅ All imports successful!")
    print(f"✅ Config initialized: {config.LM_STUDIO_API_URL}")
    print("✅ Application is ready to run!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
