from uuid import UUID, uuid4

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
