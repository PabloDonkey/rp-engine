from abc import ABC, abstractmethod
from uuid import UUID

from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind


class ScenarioSessionStore(ABC):
    """Storage interface for runtime scenario session instances."""

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        """Retrieve a scenario session by ID, or None if not found.

        Deliberately unfiltered: a superseded session must stay openable by id, which is
        what makes soft delete worth more than a purge.
        """

    @abstractmethod
    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> list[ScenarioSession]:
        """Find all scenario sessions owned by a user or group.

        Live sessions only by default, so engine callers cannot accidentally act on a
        superseded one; tooling that wants the full history opts in.
        """

    @abstractmethod
    async def find_by_definition(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        """Find an owner's **live** session running a specific scenario definition, if any."""

    @abstractmethod
    async def save(self, session: ScenarioSession) -> ScenarioSession:
        """Save or update a scenario session and return the stored value.

        The store stamps `updated_at`, so the returned session — not the argument — is the
        one that matches storage.
        """

    @abstractmethod
    async def delete(self, session_id: UUID) -> None:
        """Delete a scenario session."""

    @abstractmethod
    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        """Mark a session as the active one for an owner context."""

    @abstractmethod
    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        """Return the active session for an owner context, if any."""
