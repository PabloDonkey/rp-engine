from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresGenerationTraceStore,
    PostgresGroupIdentityStore,
    PostgresUserIdentityStore,
    create_engine,
    create_session_factory,
)
from tests.unit.infrastructure.contracts.generation_trace_store_contract import (
    assert_generation_trace_store_contract,
)
from tests.unit.infrastructure.contracts.group_identity_store_contract import (
    assert_group_identity_store_contract,
)
from tests.unit.infrastructure.contracts.user_identity_store_contract import (
    assert_user_identity_store_contract,
)

_TRUNCATE = (
    "TRUNCATE TABLE user_identities, users, group_identities, groups, generation_traces "
    "RESTART IDENTITY CASCADE"
)


async def _prepare_engine(config: PostgresConfig) -> AsyncEngine:
    engine = create_engine(config)
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    return engine


@pytest_asyncio.fixture
async def postgres_user_identity_store(
    postgres_config: PostgresConfig,
) -> AsyncIterator[PostgresUserIdentityStore]:
    engine = await _prepare_engine(postgres_config)
    yield PostgresUserIdentityStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_group_identity_store(
    postgres_config: PostgresConfig,
) -> AsyncIterator[PostgresGroupIdentityStore]:
    engine = await _prepare_engine(postgres_config)
    yield PostgresGroupIdentityStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_generation_trace_store(
    postgres_config: PostgresConfig,
) -> AsyncIterator[PostgresGenerationTraceStore]:
    engine = await _prepare_engine(postgres_config)
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
