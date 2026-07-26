import asyncio
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.community.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rp_engine.infrastructure.postgres import PostgresConfig, create_engine  # noqa: E402
from rp_engine.infrastructure.postgres.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def postgres_config() -> Iterator[PostgresConfig]:
    """A throwaway Postgres, live for the whole test session (see ADR-024).

    Backs the non-migration store contract tests (`tests/integration/infrastructure/
    test_*_contract_postgres.py`), which now run by default rather than being gated
    behind `RP_ENGINE_RUN_POSTGRES_TESTS`. The migration-integrity test manages its own
    dedicated container instead of sharing this one, since it drops/recreates the schema.
    """
    with PostgresContainer("postgres:16-alpine") as container:
        config = PostgresConfig(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            database=container.dbname,
            user=container.username,
            password=container.password,
            ssl_mode="disable",
            pool_size=5,
            max_overflow=5,
        )

        async def _create_schema() -> None:
            engine = create_engine(config)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await engine.dispose()

        asyncio.run(_create_schema())
        yield config
