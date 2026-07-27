from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.generation_trace_store import GenerationTraceStore
from rp_engine.infrastructure.postgres.models import GenerationTraceRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresGenerationTraceStore(GenerationTraceStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, *, session_id: UUID, record: dict[str, object]) -> None:
        async with session_scope(self._session_factory) as db_session:
            db_session.add(GenerationTraceRecord(id=uuid4(), session_id=session_id, record=record))

    async def delete_for_turn(self, *, session_id: UUID, turn: int) -> int:
        # `turn` is stored inside the JSONB record, so match it as text — the same way the
        # admin panel groups traces onto messages.
        statement = delete(GenerationTraceRecord).where(
            GenerationTraceRecord.session_id == session_id,
            GenerationTraceRecord.record["turn"].astext == str(turn),
        )
        async with session_scope(self._session_factory) as db_session:
            result = await db_session.execute(statement)
        return int(result.rowcount or 0)

    async def list_for_session(self, session_id: UUID) -> list[dict[str, object]]:
        statement = (
            select(GenerationTraceRecord)
            .where(GenerationTraceRecord.session_id == session_id)
            .order_by(GenerationTraceRecord.created_at.asc(), GenerationTraceRecord.id.asc())
        )
        async with self._session_factory() as db_session:
            records = (await db_session.scalars(statement)).all()
        return [record.record for record in records]
