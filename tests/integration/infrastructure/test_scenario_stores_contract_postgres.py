import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import Base
from tests.unit.infrastructure.contracts.scenario_definition_store_contract import (
    assert_minimal_scenario_round_trip,
    assert_scenario_definition_store_contract,
)
from tests.unit.infrastructure.contracts.scenario_session_store_contract import (
    assert_scenario_session_store_contract,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RP_ENGINE_RUN_POSTGRES_TESTS") != "1",
    reason="Set RP_ENGINE_RUN_POSTGRES_TESTS=1 to run PostgreSQL contract tests.",
)

_TRUNCATE = (
    "TRUNCATE TABLE active_scenario_sessions, scenario_sessions, scenario_definitions "
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
async def postgres_scenario_definition_store() -> AsyncIterator[PostgresScenarioDefinitionStore]:
    engine = await _prepare_engine()
    yield PostgresScenarioDefinitionStore(create_session_factory(engine))
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_scenario_session_store() -> AsyncIterator[PostgresScenarioSessionStore]:
    engine = await _prepare_engine()
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
