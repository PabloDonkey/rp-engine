from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from rp_engine.core.scenario.session_directives import SessionDirectives

SessionOwnerKind = Literal["user", "group"]


@dataclass(frozen=True, slots=True)
class ScenarioSession:
    """
    Runtime instance of a scenario execution.

    A scenario session represents one active roleplay with:
    - A reference to the scenario blueprint (immutable)
    - Runtime state (participants, world state, story progress)
    - Player directives (language, scenario rules, director instruction)
    - Ownership (user or group)

    Multiple independent sessions can run the same scenario.
    Session-scoped conversation history is keyed by session.id.
    """

    id: UUID
    scenario_definition_id: str
    owner_kind: SessionOwnerKind
    owner_id: UUID
    active_participants: dict[str, str] = field(default_factory=dict)
    world_state: dict[str, Any] = field(default_factory=dict)
    story_progress: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = field(default_factory=dict)
    directives: SessionDirectives = field(default_factory=SessionDirectives)

    @classmethod
    def create_for_user(
        cls,
        *,
        scenario_definition_id: str,
        user_id: UUID,
        active_participants: dict[str, str] | None = None,
        world_state: dict[str, Any] | None = None,
        story_progress: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        directives: SessionDirectives | None = None,
    ) -> "ScenarioSession":
        """Create a scenario session owned by a user."""
        return cls(
            id=uuid4(),
            scenario_definition_id=scenario_definition_id,
            owner_kind="user",
            owner_id=user_id,
            active_participants=active_participants or {},
            world_state=world_state or {},
            story_progress=story_progress or {},
            metadata=metadata or {},
            directives=directives or SessionDirectives(),
        )

    @classmethod
    def create_for_group(
        cls,
        *,
        scenario_definition_id: str,
        group_id: UUID,
        active_participants: dict[str, str] | None = None,
        world_state: dict[str, Any] | None = None,
        story_progress: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        directives: SessionDirectives | None = None,
    ) -> "ScenarioSession":
        """Create a scenario session owned by a group."""
        return cls(
            id=uuid4(),
            scenario_definition_id=scenario_definition_id,
            owner_kind="group",
            owner_id=group_id,
            active_participants=active_participants or {},
            world_state=world_state or {},
            story_progress=story_progress or {},
            metadata=metadata or {},
            directives=directives or SessionDirectives(),
        )

    def with_directives(self, directives: SessionDirectives) -> "ScenarioSession":
        """Return a copy carrying new directives; the session is otherwise unchanged."""
        return replace(self, directives=directives)
