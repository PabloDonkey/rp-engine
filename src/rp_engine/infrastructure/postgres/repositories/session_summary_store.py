from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.memory.session_summary import SessionSummary
from rp_engine.core.ports.session_summary_store import SessionSummaryStore
from rp_engine.infrastructure.postgres.models import SessionSummaryRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresSessionSummaryStore(SessionSummaryStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, session_id: UUID) -> SessionSummary | None:
        statement = select(SessionSummaryRecord).where(
            SessionSummaryRecord.session_id == session_id
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        if record is None:
            return None
        return SessionSummary(
            session_id=record.session_id,
            summary=record.summary,
            covers_through_turn=record.covers_through_turn,
            tokens=record.tokens,
            model_name=record.model_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def save(self, summary: SessionSummary) -> SessionSummary:
        """Upsert. A session has one recap, and every pass rewrites it in place.

        `created_at` is written only by the insert, so the row keeps the moment the recap
        first existed even though the worker sends a fresh value on every pass.
        """
        statement = (
            insert(SessionSummaryRecord)
            .values(
                session_id=summary.session_id,
                summary=summary.summary,
                covers_through_turn=summary.covers_through_turn,
                tokens=summary.tokens,
                model_name=summary.model_name,
                created_at=summary.created_at,
                updated_at=summary.updated_at,
            )
            .on_conflict_do_update(
                index_elements=[SessionSummaryRecord.session_id],
                set_={
                    "summary": summary.summary,
                    "covers_through_turn": summary.covers_through_turn,
                    "tokens": summary.tokens,
                    "model_name": summary.model_name,
                    "updated_at": summary.updated_at,
                },
            )
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)
        return summary
