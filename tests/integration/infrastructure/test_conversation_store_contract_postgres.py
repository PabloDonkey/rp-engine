import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresConversationStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import Base, ConversationMessageRecord
from rp_engine.infrastructure.postgres.transaction import session_scope
from tests.unit.infrastructure.contracts.conversation_store_contract import (
    assert_conversation_store_contract,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RP_ENGINE_RUN_POSTGRES_TESTS") != "1",
    reason="Set RP_ENGINE_RUN_POSTGRES_TESTS=1 to run PostgreSQL contract tests.",
)

_TRUNCATE = "TRUNCATE TABLE conversation_messages RESTART IDENTITY CASCADE"


async def _prepare_engine() -> AsyncEngine:
    settings = Settings(persistence_backend="postgres")
    config = PostgresConfig.from_settings(settings)
    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text(_TRUNCATE))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available for contract test: {exc}")
    return engine


@pytest_asyncio.fixture
async def postgres_conversation_store() -> AsyncIterator[PostgresConversationStore]:
    engine = await _prepare_engine()
    yield PostgresConversationStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_conversation_store_contract(
    postgres_conversation_store: PostgresConversationStore,
) -> None:
    await assert_conversation_store_contract(postgres_conversation_store)


@pytest.mark.asyncio
async def test_postgres_conversation_store_ties_break_on_id(
    postgres_conversation_store: PostgresConversationStore,
) -> None:
    # Two rows with an identical created_at must still sort deterministically (by id).
    session_factory = postgres_conversation_store._session_factory
    key = MemoryKey("session_tie")
    same_instant = datetime(2026, 1, 1, tzinfo=UTC)
    higher_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    lower_id = UUID("00000000-0000-0000-0000-000000000000")

    async with session_scope(session_factory) as db_session:
        db_session.add(
            ConversationMessageRecord(
                id=higher_id,
                memory_key=key.value,
                session_id=None,
                role=ConversationRole.USER.value,
                content="second by id",
                payload_metadata={},
                created_at=same_instant,
            )
        )
        db_session.add(
            ConversationMessageRecord(
                id=lower_id,
                memory_key=key.value,
                session_id=None,
                role=ConversationRole.USER.value,
                content="first by id",
                payload_metadata={},
                created_at=same_instant,
            )
        )

    loaded = await postgres_conversation_store.load_messages(key)
    assert [message.content for message in loaded] == ["first by id", "second by id"]


@pytest.mark.asyncio
async def test_postgres_conversation_store_populates_session_id_from_prefixed_key(
    postgres_conversation_store: PostgresConversationStore,
) -> None:
    session_factory = postgres_conversation_store._session_factory
    session_id = UUID("11111111-1111-1111-1111-111111111111")
    session_key = MemoryKey(f"session_{session_id}")
    plain_key = MemoryKey("adapter_scratch")
    message = ConversationMessage(role=ConversationRole.USER, content="hi", metadata={})

    await postgres_conversation_store.save_message(session_key, message)
    await postgres_conversation_store.save_message(plain_key, message)

    async with session_factory() as db_session:
        session_row = await db_session.scalar(
            select(ConversationMessageRecord).where(
                ConversationMessageRecord.memory_key == session_key.value
            )
        )
        plain_row = await db_session.scalar(
            select(ConversationMessageRecord).where(
                ConversationMessageRecord.memory_key == plain_key.value
            )
        )

    assert session_row is not None
    assert session_row.session_id == session_id
    assert plain_row is not None
    assert plain_row.session_id is None
