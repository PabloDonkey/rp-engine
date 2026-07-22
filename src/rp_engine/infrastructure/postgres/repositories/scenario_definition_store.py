from uuid import UUID

from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition


class PostgresScenarioDefinitionStore(ScenarioDefinitionStore):
    """PostgreSQL implementation of ScenarioDefinitionStore.

    Stub for Phase 3 implementation.
    """

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")

    async def save(self, scenario: ScenarioDefinition) -> None:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")

    async def delete(self, scenario_id: str) -> None:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")
