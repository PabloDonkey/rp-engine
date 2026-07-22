from abc import ABC, abstractmethod
from uuid import UUID

from rp_engine.core.scenario.scenario_definition import ScenarioDefinition


class ScenarioDefinitionStore(ABC):
    """Storage interface for reusable scenario definitions."""

    @abstractmethod
    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        """Retrieve a scenario definition by ID, or None if not found."""

    @abstractmethod
    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        """Find all scenario definitions owned by a user."""

    @abstractmethod
    async def save(self, scenario: ScenarioDefinition) -> None:
        """Save or update a scenario definition."""

    @abstractmethod
    async def delete(self, scenario_id: str) -> None:
        """Delete a scenario definition."""
