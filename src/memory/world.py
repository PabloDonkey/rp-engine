"""World state tracking (placeholder for MVP).

TODO: Implement world state with:
- Location descriptions
- Event log
- Status flags
- Environmental context
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.memory.store import JSONStore


class WorldState(BaseModel):
    """World and environment state."""

    name: str
    description: str = ""
    current_location: str = "Unknown"
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    events: list[str] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)

    def add_event(self, event: str) -> None:
        """Record a world event.

        Args:
            event: Event description
        """
        self.events.append(event)
        self.last_updated = datetime.now()

    def set_flag(self, key: str, value: Any) -> None:
        """Set a world state flag.

        Args:
            key: Flag name
            value: Flag value
        """
        self.flags[key] = value
        self.last_updated = datetime.now()

    def get_flag(self, key: str, default: Any = None) -> Any:
        """Get a world state flag.

        Args:
            key: Flag name
            default: Default value if flag doesn't exist

        Returns:
            Flag value or default
        """
        return self.flags.get(key, default)


class WorldManager:
    """Manages world state persistence."""

    def __init__(self, worlds_dir: Path) -> None:
        """Initialize world manager.

        Args:
            worlds_dir: Directory to store world files
        """
        self.worlds_dir = worlds_dir
        self.worlds_dir.mkdir(parents=True, exist_ok=True)

    def save_world(self, world: WorldState) -> None:
        """Save world state to disk.

        Args:
            world: World state to save
        """
        filepath = self.worlds_dir / f"{world.name}.json"
        JSONStore.save(filepath, world)

    def load_world(self, name: str) -> Optional[WorldState]:
        """Load world state from disk.

        Args:
            name: World name

        Returns:
            WorldState if exists, None otherwise
        """
        filepath = self.worlds_dir / f"{name}.json"

        if not JSONStore.exists(filepath):
            return None

        data = JSONStore.load(filepath)
        return WorldState.model_validate(data)

    def create_world(self, name: str, description: str = "") -> WorldState:
        """Create a new world.

        Args:
            name: World name
            description: World description

        Returns:
            New WorldState object
        """
        world = WorldState(name=name, description=description)
        self.save_world(world)
        return world
