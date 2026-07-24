import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresGenerationTraceStore,
    PostgresGroupIdentityStore,
    PostgresUserIdentityStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import Base
from tests.unit.infrastructure.contracts.generation_trace_store_contract import (
    assert_generation_trace_store_contract,
)
from tests.unit.infrastructure.contracts.group_identity_store_contract import (
    assert_group_identity_store_contract,
)
from tests.unit.infrastructure.contracts.user_identity_store_contract import (
    assert_user_identity_store_contract,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RP_ENGINE_RUN_POSTGRES_TESTS") != "1",
    reason="Set RP_ENGINE_RUN_POSTGRES_TESTS=1 to run PostgreSQL contract tests.",
)

_TRUNCATE = (
    "TRUNCATE TABLE user_identities, users, group_identities, groups, generation_traces "
    "RESTART IDENTITY CASCADE"
)


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
async def postgres_user_identity_store() -> AsyncIterator[PostgresUserIdentityStore]:
    engine = await _prepare_engine()
    yield PostgresUserIdentityStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_group_identity_store() -> AsyncIterator[PostgresGroupIdentityStore]:
    engine = await _prepare_engine()
    yield PostgresGroupIdentityStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_generation_trace_store() -> AsyncIterator[PostgresGenerationTraceStore]:
    engine = await _prepare_engine()
    yield PostgresGenerationTraceStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_user_identity_store_contract(
    postgres_user_identity_store: PostgresUserIdentityStore,
) -> None:
    await assert_user_identity_store_contract(postgres_user_identity_store)


@pytest.mark.asyncio
async def test_postgres_group_identity_store_contract(
    postgres_group_identity_store: PostgresGroupIdentityStore,
) -> None:
    await assert_group_identity_store_contract(postgres_group_identity_store)


@pytest.mark.asyncio
async def test_postgres_generation_trace_store_contract(
    postgres_generation_trace_store: PostgresGenerationTraceStore,
) -> None:
    await assert_generation_trace_store_contract(postgres_generation_trace_store)
