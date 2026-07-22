from dataclasses import dataclass, field
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.world.world import World


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """
    Immutable blueprint for a roleplay scenario.

    A scenario is a reusable template that defines:
    - The world/environment
    - Available characters and their roles
    - Scenario-specific rules
    - Initial narrative context

    Scenarios are owned by users and reused across multiple sessions.
    Multiple sessions can run the same scenario independently.
    """

    id: str
    owner_id: UUID
    name: str
    description: str
    world: World | None = None
    characters: dict[str, Character] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    initial_context: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        scenario_id: str,
        owner_id: UUID,
        name: str,
        description: str,
        world: World | None = None,
        characters: dict[str, Character] | None = None,
        rules: list[str] | None = None,
        initial_context: str = "",
        metadata: dict[str, str] | None = None,
    ) -> "ScenarioDefinition":
        """Factory method to create a scenario definition."""
        return cls(
            id=scenario_id,
            owner_id=owner_id,
            name=name,
            description=description,
            world=world,
            characters=characters or {},
            rules=rules or [],
            initial_context=initial_context,
            metadata=metadata or {},
        )
