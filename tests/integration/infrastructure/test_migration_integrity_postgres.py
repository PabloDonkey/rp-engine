import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresConversationStore,
    PostgresGenerationTraceStore,
    PostgresGroupIdentityStore,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    PostgresUserIdentityStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import Base
from tests.unit.infrastructure.contracts.conversation_store_contract import (
    assert_conversation_store_contract,
)
from tests.unit.infrastructure.contracts.generation_trace_store_contract import (
    assert_generation_trace_store_contract,
)
from tests.unit.infrastructure.contracts.group_identity_store_contract import (
    assert_group_identity_store_contract,
)
from tests.unit.infrastructure.contracts.scenario_definition_store_contract import (
    assert_minimal_scenario_round_trip,
    assert_scenario_definition_store_contract,
)
from tests.unit.infrastructure.contracts.scenario_session_store_contract import (
    assert_scenario_session_store_contract,
)
from tests.unit.infrastructure.contracts.user_identity_store_contract import (
    assert_user_identity_store_contract,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RP_ENGINE_RUN_POSTGRES_TESTS") != "1",
    reason="Set RP_ENGINE_RUN_POSTGRES_TESTS=1 to run PostgreSQL migration tests.",
)

_ROOT = Path(__file__).resolve().parents[3]
_MODEL_TABLES = set(Base.metadata.tables)


def _alembic_config() -> Config:
    return Config(str(_ROOT / "alembic.ini"))


async def _reset_schema_or_skip(engine: AsyncEngine) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available for migration test: {exc}")


@pytest_asyncio.fixture
async def migrated_engine() -> AsyncIterator[AsyncEngine]:
    settings = Settings(persistence_backend="postgres")
    config = PostgresConfig.from_settings(settings)
    engine = create_engine(config)
    await _reset_schema_or_skip(engine)

    await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
    yield engine

    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_head_creates_expected_tables(migrated_engine: AsyncEngine) -> None:
    async with migrated_engine.connect() as connection:
        table_names = await connection.run_sync(lambda conn: set(inspect(conn).get_table_names()))
    assert _MODEL_TABLES <= table_names


@pytest.mark.asyncio
async def test_migrations_match_models_with_no_autogenerate_drift(
    migrated_engine: AsyncEngine,
) -> None:
    def _compare(sync_connection: Connection) -> list[object]:
        migration_context = MigrationContext.configure(sync_connection)
        return list(compare_metadata(migration_context, Base.metadata))

    async with migrated_engine.connect() as connection:
        diff = await connection.run_sync(_compare)

    assert diff == [], f"alembic head has drifted from Base.metadata: {diff}"


@pytest.mark.asyncio
async def test_migrate_then_contract_all_stores(migrated_engine: AsyncEngine) -> None:
    # Runs the full store contract suite against a schema built by real Alembic migrations
    # (not Base.metadata.create_all), so the contracts validate the actually-deployed schema.
    session_factory = create_session_factory(migrated_engine)

    await assert_scenario_definition_store_contract(
        PostgresScenarioDefinitionStore(session_factory)
    )
    await assert_minimal_scenario_round_trip(PostgresScenarioDefinitionStore(session_factory))
    await assert_scenario_session_store_contract(PostgresScenarioSessionStore(session_factory))
    await assert_conversation_store_contract(PostgresConversationStore(session_factory))
    await assert_user_identity_store_contract(PostgresUserIdentityStore(session_factory))
    await assert_group_identity_store_contract(PostgresGroupIdentityStore(session_factory))
    await assert_generation_trace_store_contract(PostgresGenerationTraceStore(session_factory))


@pytest.mark.asyncio
async def test_migration_upgrade_downgrade_round_trip() -> None:
    settings = Settings(persistence_backend="postgres")
    config = PostgresConfig.from_settings(settings)
    engine = create_engine(config)
    await _reset_schema_or_skip(engine)

    alembic_config = _alembic_config()
    await asyncio.to_thread(command.upgrade, alembic_config, "head")
    await asyncio.to_thread(command.downgrade, alembic_config, "base")

    async with engine.connect() as connection:
        table_names = await connection.run_sync(lambda conn: set(inspect(conn).get_table_names()))
    assert not (_MODEL_TABLES & table_names), (
        f"downgrade to base left model tables behind: {_MODEL_TABLES & table_names}"
    )

    await asyncio.to_thread(command.upgrade, alembic_config, "head")
    async with engine.connect() as connection:
        table_names_after = await connection.run_sync(
            lambda conn: set(inspect(conn).get_table_names())
        )
    assert _MODEL_TABLES <= table_names_after

    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
