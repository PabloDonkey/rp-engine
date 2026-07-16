from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rp_engine.infrastructure.postgres.config import PostgresConfig


def create_engine(config: PostgresConfig) -> AsyncEngine:
    return create_async_engine(
        config.sqlalchemy_url(),
        pool_pre_ping=True,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
