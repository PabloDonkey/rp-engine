"""Session memory management with persistent storage."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from memory.store import JSONStore


class Message(BaseModel):
    """A single message in the conversation."""

    model_config = ConfigDict(frozen=True)

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionMemory(BaseModel):
    """Complete session memory with message history."""

    model_config = ConfigDict()

    session_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    character_name: str = "NPC"
    world_name: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session.

        Args:
            role: Message role ("user", "assistant", or "system")
            content: Message content
        """
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now()

    def get_last_n_messages(self, n: int = 10) -> list[Message]:
        """Get the last N messages from the session.

        Args:
            n: Number of messages to retrieve

        Returns:
            List of the last N messages
        """
        return self.messages[-n:]

    def get_all_messages(self) -> list[Message]:
        """Get all messages from the session.

        Returns:
            List of all messages
        """
        return self.messages

    def message_count(self) -> int:
        """Get the total number of messages.

        Returns:
            Number of messages in session
        """
        return len(self.messages)


class SessionManager:
    """Manages session persistence and loading."""

    def __init__(self, sessions_dir: Path) -> None:
        """Initialize session manager.

        Args:
            sessions_dir: Directory to store session files
        """
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: SessionMemory) -> None:
        """Save session to disk.

        Args:
            session: Session to save
        """
        filepath = self.sessions_dir / f"{session.session_id}.json"
        JSONStore.save(filepath, session)

    def load_session(self, session_id: str) -> Optional[SessionMemory]:
        """Load session from disk.

        Args:
            session_id: ID of session to load

        Returns:
            SessionMemory if exists, None otherwise
        """
        filepath = self.sessions_dir / f"{session_id}.json"

        if not JSONStore.exists(filepath):
            return None

        data = JSONStore.load(filepath)
        return SessionMemory.model_validate(data)

    def create_session(
        self,
        session_id: str,
        character_name: str = "NPC",
        world_name: Optional[str] = None,
    ) -> SessionMemory:
        """Create a new session.

        Args:
            session_id: Unique identifier for the session
            character_name: Name of the character in this session
            world_name: Optional name of the world/setting

        Returns:
            New SessionMemory object
        """
        session = SessionMemory(
            session_id=session_id,
            character_name=character_name,
            world_name=world_name,
        )
        self.save_session(session)
        return session

    def list_sessions(self) -> list[str]:
        """List all saved session IDs.

        Returns:
            List of session IDs
        """
        json_files = self.sessions_dir.glob("*.json")
        return [f.stem for f in json_files]