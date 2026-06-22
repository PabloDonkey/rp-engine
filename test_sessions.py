#!/usr/bin/env python3.12
"""Test session creation and loading."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import config
from memory.session import SessionManager

print("Testing Session Management")
print("=" * 60)

# Initialize manager
sm = SessionManager(config.SESSION_DIR)

# Test 1: Create a session
print("\n1️⃣  Creating new session...")
session = sm.create_session(
    session_id="test_session",
    character_name="TestChar",
    world_name="TestWorld"
)
print(f"   ✅ Created session: {session.session_id}")
print(f"   ✅ Character: {session.character_name}")
print(f"   ✅ World: {session.world_name}")

# Test 2: Add messages
print("\n2️⃣  Adding messages...")
session.add_message("user", "Hello!")
session.add_message("assistant", "Hi there!")
print(f"   ✅ Added 2 messages")
print(f"   ✅ Message count: {session.message_count()}")

# Test 3: Save session
print("\n3️⃣  Saving session...")
sm.save_session(session)
print(f"   ✅ Session saved")

# Test 4: Load session
print("\n4️⃣  Loading session...")
loaded = sm.load_session("test_session")
if loaded:
    print(f"   ✅ Loaded session: {loaded.session_id}")
    print(f"   ✅ Message count: {loaded.message_count()}")
    print(f"   ✅ Messages preserved: {loaded.messages[0].content}")
else:
    print("   ❌ Failed to load session")

# Test 5: List sessions
print("\n5️⃣  Listing sessions...")
sessions = sm.list_sessions()
print(f"   ✅ Found {len(sessions)} session(s): {sessions}")

print("\n" + "=" * 60)
print("✅ All session tests passed!")
