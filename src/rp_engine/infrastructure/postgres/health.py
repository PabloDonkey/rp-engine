import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class PostgresHealthProbe:
    """Lightweight connectivity + schema-version check, kept out of core (no port needed —
    it's an operational concern of the postgres backend, not something the domain depends on).
    """

    def __init__(self, engine: AsyncEngine, alembic_ini_path: Path | None = None) -> None:
        self._engine = engine
        self._alembic_ini_path = alembic_ini_path

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            logger.exception("PostgreSQL connectivity check failed")
            return False
        return True

    async def check_schema_version(self) -> None:
        """Best-effort: warn (never raise) if the DB's stamped Alembic revision doesn't match
        the code's head. Silently skips if alembic.ini can't be found.
        """
        if self._alembic_ini_path is None or not self._alembic_ini_path.exists():
            return

        try:
            async with self._engine.connect() as connection:
                result = await connection.execute(text("SELECT version_num FROM alembic_version"))
                row = result.first()
        except Exception:
            logger.warning("Could not read alembic_version to check schema version", exc_info=True)
            return

        stamped_revision = row[0] if row is not None else None
        script = ScriptDirectory.from_config(Config(str(self._alembic_ini_path)))
        heads = script.get_heads()
        expected_head = heads[0] if len(heads) == 1 else None

        if stamped_revision != expected_head:
            logger.warning(
                "Database schema revision does not match the code's Alembic head",
                extra={"db_revision": stamped_revision, "expected_head": expected_head},
            )
