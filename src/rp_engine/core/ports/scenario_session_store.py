from abc import ABC, abstractmethod
from uuid import UUID

from rp_engine.core.scenario.scenario_session import ScenarioSession


class ScenarioSessionStore(ABC):
    """Storage interface for runtime scenario session instances."""

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        """Retrieve a scenario session by ID, or None if not found."""

    @abstractmethod
    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
    ) -> list[ScenarioSession]:
        """Find all scenario sessions owned by a user or group."""

    @abstractmethod
    async def save(self, session: ScenarioSession) -> None:
        """Save or update a scenario session."""

    @abstractmethod
    async def delete(self, session_id: UUID) -> None:
        """Delete a scenario session."""
