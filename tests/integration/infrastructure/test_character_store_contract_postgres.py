import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text

from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import (
    PostgresCharacterStore,
    PostgresConfig,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import Base
from tests.unit.infrastructure.contracts.character_store_contract import (
    assert_character_store_contract,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RP_ENGINE_RUN_POSTGRES_TESTS") != "1",
    reason="Set RP_ENGINE_RUN_POSTGRES_TESTS=1 to run PostgreSQL contract tests.",
)


@pytest_asyncio.fixture
async def postgres_character_store() -> AsyncIterator[PostgresCharacterStore]:
    settings = Settings(persistence_backend="postgres")
    config = PostgresConfig.from_settings(settings)
    engine = create_engine(config)

    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("TRUNCATE TABLE characters RESTART IDENTITY CASCADE"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available for contract test: {exc}")

    session_factory = create_session_factory(engine)
    yield PostgresCharacterStore(session_factory)

    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE characters RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_character_store_contract(
    postgres_character_store: PostgresCharacterStore,
) -> None:
    await assert_character_store_contract(postgres_character_store)
