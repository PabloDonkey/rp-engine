from datetime import UTC
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind
from rp_engine.infrastructure.postgres.models import (
    ActiveScenarioSessionRecord,
    ScenarioSessionRecord,
)
from rp_engine.infrastructure.postgres.transaction import session_scope
from rp_engine.infrastructure.scenario_serialization import scenario_session_from_payload


class PostgresScenarioSessionStore(ScenarioSessionStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        statement = select(ScenarioSessionRecord).where(ScenarioSessionRecord.id == session_id)
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
    ) -> list[ScenarioSession]:
        statement = select(ScenarioSessionRecord).where(
            ScenarioSessionRecord.owner_kind == owner_kind,
            ScenarioSessionRecord.owner_id == owner_id,
        )
        async with self._session_factory() as db_session:
            records = (await db_session.scalars(statement)).all()
        return [session for record in records if (session := self._to_domain(record)) is not None]

    async def find_by_definition(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        statement = select(ScenarioSessionRecord).where(
            ScenarioSessionRecord.owner_kind == owner_kind,
            ScenarioSessionRecord.owner_id == owner_id,
            ScenarioSessionRecord.scenario_definition_id == scenario_definition_id,
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        values = {
            "id": session.id,
            "scenario_definition_id": session.scenario_definition_id,
            "owner_kind": session.owner_kind,
            "owner_id": session.owner_id,
            "active_participants": dict(session.active_participants),
            "world_state": dict(session.world_state),
            "story_progress": dict(session.story_progress),
            "created_at": session.created_at,
            "payload_metadata": dict(session.metadata),
        }
        statement = insert(ScenarioSessionRecord).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[ScenarioSessionRecord.id],
            set_={
                "scenario_definition_id": statement.excluded.scenario_definition_id,
                "owner_kind": statement.excluded.owner_kind,
                "owner_id": statement.excluded.owner_id,
                "active_participants": statement.excluded.active_participants,
                "world_state": statement.excluded.world_state,
                "story_progress": statement.excluded.story_progress,
                "created_at": statement.excluded.created_at,
                "metadata": statement.excluded.metadata,
            },
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)
        return session

    async def delete(self, session_id: UUID) -> None:
        statement = delete(ScenarioSessionRecord).where(ScenarioSessionRecord.id == session_id)
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        statement = insert(ActiveScenarioSessionRecord).values(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=session_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[
                ActiveScenarioSessionRecord.owner_kind,
                ActiveScenarioSessionRecord.owner_id,
            ],
            set_={"session_id": statement.excluded.session_id},
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        statement = (
            select(ScenarioSessionRecord)
            .join(
                ActiveScenarioSessionRecord,
                ActiveScenarioSessionRecord.session_id == ScenarioSessionRecord.id,
            )
            .where(
                ActiveScenarioSessionRecord.owner_kind == owner_kind,
                ActiveScenarioSessionRecord.owner_id == owner_id,
            )
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: ScenarioSessionRecord | None) -> ScenarioSession | None:
        if record is None:
            return None
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        payload = {
            "id": str(record.id),
            "scenario_definition_id": record.scenario_definition_id,
            "owner_kind": record.owner_kind,
            "owner_id": str(record.owner_id),
            "active_participants": record.active_participants or {},
            "world_state": record.world_state or {},
            "story_progress": record.story_progress or {},
            "created_at": created_at.isoformat(),
            "metadata": record.payload_metadata or {},
        }
        return scenario_session_from_payload(payload)
