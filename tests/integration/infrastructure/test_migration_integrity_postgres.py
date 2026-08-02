import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.community.postgres import PostgresContainer

from alembic import command
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

_ROOT = Path(__file__).resolve().parents[3]
_MODEL_TABLES = set(Base.metadata.tables)


def _alembic_config() -> Config:
    return Config(str(_ROOT / "alembic.ini"))


def _point_alembic_env_at(monkeypatch: pytest.MonkeyPatch, config: PostgresConfig) -> None:
    """`alembic/env.py` builds its own `Settings()` from the environment, ignoring
    anything set on the `Config` object passed to `command.upgrade`/`downgrade` — so the
    only way to target the testcontainers instance is via these env vars."""
    monkeypatch.setenv("RP_ENGINE_POSTGRES_HOST", config.host)
    monkeypatch.setenv("RP_ENGINE_POSTGRES_PORT", str(config.port))
    monkeypatch.setenv("RP_ENGINE_POSTGRES_DATABASE", config.database)
    monkeypatch.setenv("RP_ENGINE_POSTGRES_USER", config.user)
    monkeypatch.setenv("RP_ENGINE_POSTGRES_PASSWORD", config.password)


async def _reset_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="module")
def migration_postgres_config() -> Iterator[PostgresConfig]:
    """A dedicated container, separate from the shared `postgres_config` fixture.

    This suite drops/recreates the `public` schema around real Alembic upgrade/downgrade
    cycles, which would destroy the tables the other (non-migration) contract tests share
    a single container for.
    """
    with PostgresContainer("postgres:16-alpine") as container:
        yield PostgresConfig(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            database=container.dbname,
            user=container.username,
            password=container.password,
            ssl_mode="disable",
            pool_size=5,
            max_overflow=5,
        )


@pytest_asyncio.fixture
async def migrated_engine(
    migration_postgres_config: PostgresConfig, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncEngine]:
    _point_alembic_env_at(monkeypatch, migration_postgres_config)
    engine = create_engine(migration_postgres_config)
    await _reset_schema(engine)

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


_PRE_S020_REVISION = "20260727_0010"

_INSERT_PRE_S020_SESSION = """
INSERT INTO scenario_sessions (
    id, scenario_definition_id, owner_kind, owner_id,
    active_participants, world_state, story_progress,
    created_at, updated_at, metadata, directives
) VALUES (
    :id, 'vault', 'user', :owner_id,
    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
    now(), now(), '{}'::jsonb, CAST(:directives AS jsonb)
)
"""


@pytest.mark.asyncio
async def test_pre_s020_director_notes_are_converted_to_a_queue(
    migration_postgres_config: PostgresConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration `20260802_0011` has to move the *data*, not just the code.

    A row left in the pre-S020 single-string shape reads back as an empty queue, so the
    player's armed note would vanish on the next load — the same "code fixed, data not"
    failure `20260727_0010` existed to clean up after.
    """
    _point_alembic_env_at(monkeypatch, migration_postgres_config)
    engine = create_engine(migration_postgres_config)
    await _reset_schema(engine)
    alembic_config = _alembic_config()

    await asyncio.to_thread(command.upgrade, alembic_config, _PRE_S020_REVISION)

    armed = UUID("00000000-0000-0000-0000-0000000000a1")
    empty = UUID("00000000-0000-0000-0000-0000000000a2")
    async with engine.begin() as connection:
        for session_id, directives in (
            (armed, '{"language": "fr", "rules": [], "director_instruction": "Raise the stakes."}'),
            (empty, '{"language": "auto", "rules": [], "director_instruction": ""}'),
        ):
            await connection.execute(
                text(_INSERT_PRE_S020_SESSION),
                {"id": session_id, "owner_id": session_id, "directives": directives},
            )

    await asyncio.to_thread(command.upgrade, alembic_config, "head")

    async with engine.connect() as connection:
        converted = dict(
            (row.id, row.directives)
            for row in (
                await connection.execute(text("SELECT id, directives FROM scenario_sessions"))
            ).all()
        )

    assert converted[armed]["director_instructions"] == ["Raise the stakes."]
    assert converted[empty]["director_instructions"] == []
    # The old key is gone, not merely shadowed — a stale copy would be read by nothing and
    # quietly diverge from the queue.
    assert "director_instruction" not in converted[armed]
    assert "director_instruction" not in converted[empty]
    # Untouched keys survive the rewrite.
    assert converted[armed]["language"] == "fr"

    await asyncio.to_thread(command.downgrade, alembic_config, _PRE_S020_REVISION)

    async with engine.connect() as connection:
        reverted = dict(
            (row.id, row.directives)
            for row in (
                await connection.execute(text("SELECT id, directives FROM scenario_sessions"))
            ).all()
        )

    assert reverted[armed]["director_instruction"] == "Raise the stakes."
    assert reverted[empty]["director_instruction"] == ""
    assert "director_instructions" not in reverted[armed]

    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_upgrade_downgrade_round_trip(
    migration_postgres_config: PostgresConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_alembic_env_at(monkeypatch, migration_postgres_config)
    engine = create_engine(migration_postgres_config)
    await _reset_schema(engine)

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
