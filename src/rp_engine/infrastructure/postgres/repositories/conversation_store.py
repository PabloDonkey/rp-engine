from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.conversation.builder import ConversationBuilder
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.infrastructure.postgres.models import ConversationMessageRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresConversationStore(ConversationStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        record = ConversationMessageRecord(
            id=uuid4(),
            memory_key=memory_key.value,
            session_id=self._extract_session_id(memory_key),
            role=message.role.value,
            content=message.content,
            payload_metadata=message.metadata,
        )
        async with session_scope(self._session_factory) as db_session:
            db_session.add(record)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        statement = (
            select(ConversationMessageRecord)
            .where(ConversationMessageRecord.memory_key == memory_key.value)
            .order_by(
                ConversationMessageRecord.created_at.asc(),
                ConversationMessageRecord.id.asc(),
            )
        )
        async with self._session_factory() as db_session:
            rows = (await db_session.scalars(statement)).all()

        messages: list[ConversationMessage] = []
        for row in rows:
            converted = self._to_domain(row)
            if converted is not None:
                messages.append(converted)
        return messages

    @staticmethod
    def _to_domain(record: ConversationMessageRecord) -> ConversationMessage | None:
        metadata: dict[str, str] = {}
        if isinstance(record.payload_metadata, dict):
            metadata = {
                key: value
                for key, value in record.payload_metadata.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        return ConversationBuilder.message_from_storage(
            role=record.role,
            content=record.content,
            metadata=metadata,
        )

    async def delete_last_message(
        self, memory_key: MemoryKey
    ) -> ConversationMessage | None:
        statement = (
            select(ConversationMessageRecord)
            .where(ConversationMessageRecord.memory_key == memory_key.value)
            # Mirrors `load_messages`' ordering exactly, so "the last message" means the same
            # row the transcript shows last.
            .order_by(
                ConversationMessageRecord.created_at.desc(),
                ConversationMessageRecord.id.desc(),
            )
            .limit(1)
        )
        async with session_scope(self._session_factory) as db_session:
            record = await db_session.scalar(statement)
            if record is None:
                return None
            message = self._to_domain(record)
            await db_session.delete(record)
        return message

    async def clear(self, memory_key: MemoryKey) -> None:
        statement = delete(ConversationMessageRecord).where(
            ConversationMessageRecord.memory_key == memory_key.value
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    @staticmethod
    def _extract_session_id(memory_key: MemoryKey) -> UUID | None:
        value = memory_key.value
        if not value.startswith("session_"):
            return None
        raw_session_id = value.removeprefix("session_").strip()
        if not raw_session_id:
            return None
        try:
            return UUID(raw_session_id)
        except ValueError:
            return None
