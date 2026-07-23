from dataclasses import dataclass, field
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.scenario.story_graph import StoryGraph
from rp_engine.core.scenario.visibility import ScenarioVisibility
from rp_engine.core.world.world import World


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """
    Immutable blueprint for a roleplay scenario.

    A scenario is a reusable template that defines:
    - The world/environment (optional)
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
    characters: dict[str, Character] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    story_graph: StoryGraph | None = None
    initial_context: str = ""
    visibility: ScenarioVisibility = ScenarioVisibility.PUBLIC
    # Telegram chat ids allowed to see/play a RESTRICTED scenario. Empty for other
    # visibilities. Ignored unless visibility is RESTRICTED.
    allowed_group_chat_ids: tuple[str, ...] = ()
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
        story_graph: StoryGraph | None = None,
        initial_context: str = "",
        visibility: ScenarioVisibility = ScenarioVisibility.PUBLIC,
        allowed_group_chat_ids: tuple[str, ...] = (),
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
            story_graph=story_graph,
            initial_context=initial_context,
            visibility=visibility,
            allowed_group_chat_ids=allowed_group_chat_ids,
            metadata=metadata or {},
        )

    def _allows_caller(self, caller_group_chat_id: str | None) -> bool:
        """Whether a RESTRICTED scenario admits this caller's group chat id."""
        return (
            caller_group_chat_id is not None
            and caller_group_chat_id in self.allowed_group_chat_ids
        )

    def is_listed_for(self, caller_group_chat_id: str | None) -> bool:
        """Whether this scenario should appear in the caller's /scenarios listing."""
        if self.visibility is ScenarioVisibility.PUBLIC:
            return True
        if self.visibility is ScenarioVisibility.UNLISTED:
            return False
        return self._allows_caller(caller_group_chat_id)

    def is_playable_by(self, caller_group_chat_id: str | None) -> bool:
        """Whether the caller may start a playthrough of this scenario via /play."""
        if self.visibility is ScenarioVisibility.RESTRICTED:
            return self._allows_caller(caller_group_chat_id)
        # PUBLIC and UNLISTED are both playable by anyone who knows the id.
        return True
