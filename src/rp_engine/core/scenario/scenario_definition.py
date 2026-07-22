from dataclasses import dataclass, field
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.scenario.role_profile import RoleProfile
from rp_engine.core.scenario.story_graph import StoryGraph
from rp_engine.core.world.world import World


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """
    Immutable blueprint for a roleplay scenario.

    A scenario is a reusable template that defines:
    - The world/environment (optional)
    - Role profiles: abstract roles the scenario expects (optional)
    - Characters: concrete reusable characters, keyed by role (optional)
    - Scenario-specific rules
    - An optional story graph describing narrative structure
    - Initial narrative context

    Scenarios are owned by users and reused across multiple sessions. Multiple
    sessions can run the same scenario independently, each with its own runtime
    state (see ScenarioSession).

    Everything on this type is definition data. It carries no runtime state.
    """

    id: str
    owner_id: UUID
    name: str
    description: str
    world: World | None = None
    role_profiles: dict[str, RoleProfile] = field(default_factory=dict)
    characters: dict[str, Character] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    story_graph: StoryGraph | None = None
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
        role_profiles: dict[str, RoleProfile] | None = None,
        characters: dict[str, Character] | None = None,
        rules: list[str] | None = None,
        story_graph: StoryGraph | None = None,
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
            role_profiles=role_profiles or {},
            characters=characters or {},
            rules=rules or [],
            story_graph=story_graph,
            initial_context=initial_context,
            metadata=metadata or {},
        )
