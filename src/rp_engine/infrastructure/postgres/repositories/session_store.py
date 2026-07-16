from datetime import UTC
from typing import cast
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.session_store import SessionStore
from rp_engine.core.session.session import Session, SessionOwnerKind
from rp_engine.infrastructure.postgres.models import ActiveSessionRecord, SessionRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresSessionStore(SessionStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, session_id: UUID) -> Session | None:
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def find_by_relationship(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None:
        statement: Select[tuple[SessionRecord]] = select(SessionRecord).where(
            SessionRecord.owner_kind == owner_kind,
            SessionRecord.owner_id == owner_id,
            SessionRecord.character_id == character_id,
            SessionRecord.world_id == world_id,
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def save(self, session: Session) -> Session:
        values = {
            "id": session.id,
            "owner_kind": session.owner_kind,
            "owner_id": session.owner_id,
            "character_id": session.character_id,
            "world_id": session.world_id,
            "created_at": session.created_at,
            "metadata": session.metadata,
        }
        statement = insert(SessionRecord).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[SessionRecord.id],
            set_={
                "owner_kind": statement.excluded.owner_kind,
                "owner_id": statement.excluded.owner_id,
                "character_id": statement.excluded.character_id,
                "world_id": statement.excluded.world_id,
                "created_at": statement.excluded.created_at,
                "metadata": statement.excluded.metadata,
            },
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)
        return session

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        statement = insert(ActiveSessionRecord).values(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=session_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ActiveSessionRecord.owner_kind, ActiveSessionRecord.owner_id],
            set_={"session_id": statement.excluded.session_id},
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> Session | None:
        statement = select(SessionRecord).join(
            ActiveSessionRecord,
            ActiveSessionRecord.session_id == SessionRecord.id,
        ).where(
            ActiveSessionRecord.owner_kind == owner_kind,
            ActiveSessionRecord.owner_id == owner_id,
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: SessionRecord | None) -> Session | None:
        if record is None:
            return None
        if record.owner_kind not in {"user", "group"}:
            return None
        owner_kind = cast(SessionOwnerKind, record.owner_kind)
        metadata: dict[str, str] = {}
        raw_metadata = record.payload_metadata
        if isinstance(raw_metadata, dict):
            metadata = {
                key: value
                for key, value in raw_metadata.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return Session(
            id=record.id,
            owner_kind=owner_kind,
            owner_id=record.owner_id,
            character_id=record.character_id,
            world_id=record.world_id,
            created_at=created_at,
            metadata=metadata,
        )
