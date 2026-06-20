"""Basic tests for rp-engine modules."""

import pytest
from pathlib import Path
from datetime import datetime

from memory.session import Message, SessionMemory
from memory.character import CharacterState
from memory.world import WorldState


class TestMessage:
    """Test Message model."""

    def test_message_creation(self) -> None:
        """Test creating a message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)


class TestSessionMemory:
    """Test SessionMemory model."""

    def test_session_creation(self) -> None:
        """Test creating a session."""
        session = SessionMemory(session_id="test_session")
        assert session.session_id == "test_session"
        assert session.message_count() == 0

    def test_add_message(self) -> None:
        """Test adding messages to session."""
        session = SessionMemory(session_id="test_session")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert session.message_count() == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_get_last_n_messages(self) -> None:
        """Test retrieving last N messages."""
        session = SessionMemory(session_id="test_session")
        for i in range(10):
            session.add_message("user", f"Message {i}")

        last_5 = session.get_last_n_messages(5)
        assert len(last_5) == 5
        assert last_5[0].content == "Message 5"
        assert last_5[4].content == "Message 9"


class TestCharacterState:
    """Test CharacterState model."""

    def test_character_creation(self) -> None:
        """Test creating a character."""
        char = CharacterState(name="Aldric", personality="Cynical")
        assert char.name == "Aldric"
        assert char.personality == "Cynical"
        assert char.relationship_level == 0.0

    def test_relationship_update(self) -> None:
        """Test updating relationship."""
        char = CharacterState(name="Aldric")
        char.update_relationship(10.0)
        assert char.relationship_level == 10.0

        char.update_relationship(-30.0)
        assert char.relationship_level == -20.0

        # Test bounds
        char.update_relationship(150.0)
        assert char.relationship_level == 100.0  # Capped at max


class TestWorldState:
    """Test WorldState model."""

    def test_world_creation(self) -> None:
        """Test creating a world."""
        world = WorldState(name="Tavern District")
        assert world.name == "Tavern District"
        assert len(world.events) == 0

    def test_add_event(self) -> None:
        """Test adding events."""
        world = WorldState(name="Test World")
        world.add_event("A stranger entered")
        world.add_event("Commotion at the bar")

        assert len(world.events) == 2
        assert world.events[0] == "A stranger entered"

    def test_flags(self) -> None:
        """Test setting and getting flags."""
        world = WorldState(name="Test World")
        world.set_flag("tavern_open", True)
        world.set_flag("population", 42)

        assert world.get_flag("tavern_open") is True
        assert world.get_flag("population") == 42
        assert world.get_flag("nonexistent", "default") == "default"
