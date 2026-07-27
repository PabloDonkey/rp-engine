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
    - The player's own persona (name + description, immutable once set)
    - Ownership (user or group)
    - A lifecycle: `deleted_at is None` means "this is the live session"; a session
      superseded by `/restart` or `/clear` keeps its row and transcript but stops being
      found by the lookups the engine uses to resume (ADR-025).

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
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    directives: SessionDirectives = field(default_factory=SessionDirectives)
    user_persona_name: str | None = None
    user_persona_description: str | None = None

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
        user_persona_name: str | None = None,
        user_persona_description: str | None = None,
    ) -> "ScenarioSession":
        """Create a scenario session owned by a user."""
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            scenario_definition_id=scenario_definition_id,
            owner_kind="user",
            owner_id=user_id,
            active_participants=active_participants or {},
            world_state=world_state or {},
            story_progress=story_progress or {},
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            directives=directives or SessionDirectives(),
            user_persona_name=user_persona_name,
            user_persona_description=user_persona_description,
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
        user_persona_name: str | None = None,
        user_persona_description: str | None = None,
    ) -> "ScenarioSession":
        """Create a scenario session owned by a group."""
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            scenario_definition_id=scenario_definition_id,
            owner_kind="group",
            owner_id=group_id,
            active_participants=active_participants or {},
            world_state=world_state or {},
            story_progress=story_progress or {},
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            directives=directives or SessionDirectives(),
            user_persona_name=user_persona_name,
            user_persona_description=user_persona_description,
        )

    @property
    def has_persona(self) -> bool:
        return bool(self.user_persona_name)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def resolve_user_name(self, fallback: str) -> str:
        """What `{{user}}` means for this session: the player's persona name once they have
        chosen one, otherwise the transport's display name for the owner."""
        return self.user_persona_name or fallback

    def with_directives(self, directives: SessionDirectives) -> "ScenarioSession":
        """Return a copy carrying new directives; the session is otherwise unchanged."""
        return replace(self, directives=directives)

    def with_persona(self, *, name: str, description: str = "") -> "ScenarioSession":
        """Attach the player's persona. A session accepts one exactly once.

        Immutability is the point: the name is substituted for `{{user}}` in every prompt
        and in the transcript already written, so letting it change mid-story would rewrite
        history. Changing persona means a new session, which is what `/clear` gives you.
        """
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Persona name must not be empty.")
        if self.has_persona:
            raise ValueError(
                f"Session {self.id} already has a persona; personas are immutable once set."
            )
        cleaned_description = description.strip()
        return replace(
            self,
            user_persona_name=cleaned_name,
            user_persona_description=cleaned_description or None,
        )

    def mark_deleted(self, *, at: datetime | None = None) -> "ScenarioSession":
        """Return a copy stamped as superseded. Idempotent — an already-superseded session
        keeps its original timestamp, so the record of *when* it ended stays true."""
        if self.deleted_at is not None:
            return self
        return replace(self, deleted_at=at or datetime.now(UTC))
