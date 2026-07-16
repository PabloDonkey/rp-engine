from dataclasses import dataclass
from urllib.parse import quote_plus

from rp_engine.infrastructure.config.settings import Settings


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl_mode: str
    pool_size: int
    max_overflow: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "PostgresConfig":
        return cls(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_database,
            user=settings.postgres_user,
            password=settings.postgres_password,
            ssl_mode=settings.postgres_ssl_mode,
            pool_size=settings.postgres_pool_size,
            max_overflow=settings.postgres_max_overflow,
        )

    def sqlalchemy_url(self) -> str:
        quoted_user = quote_plus(self.user)
        quoted_password = quote_plus(self.password)
        query = ""
        if self.ssl_mode == "require":
            query = "?sslmode=require"
        return (
            "postgresql+asyncpg://"
            f"{quoted_user}:{quoted_password}@{self.host}:{self.port}/{self.database}{query}"
        )
