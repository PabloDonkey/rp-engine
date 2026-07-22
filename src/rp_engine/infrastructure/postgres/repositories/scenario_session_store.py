from uuid import UUID

from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind

_NOT_IMPLEMENTED = "PostgreSQL scenario persistence not yet implemented"


class PostgresScenarioSessionStore(ScenarioSessionStore):
    """PostgreSQL implementation of ScenarioSessionStore.

    Stub for Phase 3 implementation.
    """

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
    ) -> list[ScenarioSession]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def find_by_definition(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def delete(self, session_id: UUID) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)
