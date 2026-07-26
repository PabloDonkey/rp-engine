from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    create_engine,
    create_session_factory,
)
from tests.unit.infrastructure.contracts.scenario_definition_store_contract import (
    assert_minimal_scenario_round_trip,
    assert_scenario_definition_store_contract,
)
from tests.unit.infrastructure.contracts.scenario_session_store_contract import (
    assert_scenario_session_store_contract,
)

_TRUNCATE = (
    "TRUNCATE TABLE active_scenario_sessions, scenario_sessions, scenario_definitions "
    "RESTART IDENTITY CASCADE"
)


async def _prepare_engine(config: PostgresConfig) -> AsyncEngine:
    engine = create_engine(config)
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    return engine


@pytest_asyncio.fixture
async def postgres_scenario_definition_store(
    postgres_config: PostgresConfig,
) -> AsyncIterator[PostgresScenarioDefinitionStore]:
    engine = await _prepare_engine(postgres_config)
    yield PostgresScenarioDefinitionStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_scenario_session_store(
    postgres_config: PostgresConfig,
) -> AsyncIterator[PostgresScenarioSessionStore]:
    engine = await _prepare_engine(postgres_config)
    yield PostgresScenarioSessionStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_scenario_definition_store_contract(
    postgres_scenario_definition_store: PostgresScenarioDefinitionStore,
) -> None:
    await assert_scenario_definition_store_contract(postgres_scenario_definition_store)
    await assert_minimal_scenario_round_trip(postgres_scenario_definition_store)


@pytest.mark.asyncio
async def test_postgres_scenario_session_store_contract(
    postgres_scenario_session_store: PostgresScenarioSessionStore,
) -> None:
    await assert_scenario_session_store_contract(postgres_scenario_session_store)
