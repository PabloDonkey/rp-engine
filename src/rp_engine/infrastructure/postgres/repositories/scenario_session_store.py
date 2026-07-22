from uuid import UUID

from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession


class PostgresScenarioSessionStore(ScenarioSessionStore):
    """PostgreSQL implementation of ScenarioSessionStore.

    Stub for Phase 3 implementation.
    """

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")

    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
    ) -> list[ScenarioSession]:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")

    async def save(self, session: ScenarioSession) -> None:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")

    async def delete(self, session_id: UUID) -> None:
        raise NotImplementedError("PostgreSQL scenario persistence not yet implemented")
