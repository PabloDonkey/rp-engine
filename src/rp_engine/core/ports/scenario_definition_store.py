from abc import ABC, abstractmethod
from uuid import UUID

from rp_engine.core.scenario.scenario_definition import ScenarioDefinition


class ScenarioDefinitionStore(ABC):
    """Storage interface for reusable scenario definitions.

    Retirement is a soft delete, and one invariant makes it safe: **`save()` never writes
    `deleted_at`**. Only `delete` and `restore` change it. The boot import calls `save()`
    for every catalog file at every start, and an admin edit calls `save()` too, so a
    `save()` that carried the stamp would bring a retired curated scenario back at the next
    restart.
    """

    @abstractmethod
    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        """Retrieve a scenario definition by ID, or None if not found.

        A retired scenario still resolves here. Stories already running it must keep
        playing, and an export must still be able to read it.
        """

    @abstractmethod
    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        """Find all scenario definitions owned by a user."""

    @abstractmethod
    async def list_all(self, *, include_inactive: bool = False) -> list[ScenarioDefinition]:
        """All scenario definitions, regardless of owner.

        Scenarios are a single shared library (curated + hand-authored), not
        per-user-scoped content — listing/`/play` visibility is controlled by
        `ScenarioVisibility`, not by ownership. See ADR-024.

        Retired scenarios are left out unless `include_inactive` asks for them.
        """

    @abstractmethod
    async def save(self, scenario: ScenarioDefinition) -> None:
        """Save or update a scenario definition. Never writes `deleted_at`."""

    @abstractmethod
    async def delete(self, scenario_id: str) -> None:
        """Retire a scenario. The row stays; `deleted_at` is stamped.

        Idempotent: a scenario that is already retired keeps its original stamp, so the
        record of *when* it was retired stays true.
        """

    @abstractmethod
    async def restore(self, scenario_id: str) -> None:
        """Bring a retired scenario back. Clears `deleted_at`. Idempotent."""
