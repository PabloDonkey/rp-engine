from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresLorebookStore,
    PostgresScenarioDefinitionStore,
    create_engine,
    create_session_factory,
)
from tests.unit.infrastructure.contracts.lorebook_store_contract import (
    assert_lorebook_store_contract,
    assert_lorebook_store_matching_contract,
)

_TRUNCATE = "TRUNCATE TABLE lorebook_entries, scenario_definitions RESTART IDENTITY CASCADE"


async def _prepare_engine(config: PostgresConfig) -> AsyncEngine:
    engine = create_engine(config)
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    return engine


@pytest_asyncio.fixture
async def postgres_lorebook_stores(
    postgres_config: PostgresConfig,
) -> AsyncIterator[tuple[PostgresLorebookStore, PostgresScenarioDefinitionStore]]:
    engine = await _prepare_engine(postgres_config)
    factory = create_session_factory(engine)
    yield PostgresLorebookStore(factory), PostgresScenarioDefinitionStore(factory)
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_lorebook_store_contract(
    postgres_lorebook_stores: tuple[PostgresLorebookStore, PostgresScenarioDefinitionStore],
) -> None:
    lorebook_store, definition_store = postgres_lorebook_stores
    await assert_lorebook_store_contract(lorebook_store, definition_store=definition_store)


@pytest.mark.asyncio
async def test_postgres_lorebook_store_matching_contract(
    postgres_lorebook_stores: tuple[PostgresLorebookStore, PostgresScenarioDefinitionStore],
) -> None:
    lorebook_store, definition_store = postgres_lorebook_stores
    await assert_lorebook_store_matching_contract(lorebook_store, definition_store=definition_store)
