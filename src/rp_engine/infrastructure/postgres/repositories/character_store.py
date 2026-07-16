from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.ports.character_store import CharacterStore
from rp_engine.infrastructure.postgres.models import CharacterRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresCharacterStore(CharacterStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, character_id: str) -> Character | None:
        statement = select(CharacterRecord).where(CharacterRecord.character_id == character_id)
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def find_by_name(self, name: str) -> Character | None:
        target = name.strip().lower()
        statement = select(CharacterRecord).where(func.lower(CharacterRecord.name) == target)
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def create_minimal(
        self,
        *,
        character_id: str,
        owner_id: UUID,
        name: str,
        visibility: CharacterVisibility = CharacterVisibility.PRIVATE,
    ) -> Character:
        existing = await self.get_by_id(character_id)
        if existing is not None:
            return existing

        values = {
            "pk": uuid4(),
            "character_id": character_id,
            "owner_id": owner_id,
            "visibility": visibility.value,
            "name": name,
            "description": f"Character profile for {name}.",
            "personality": "Open-ended roleplay persona.",
            "greeting": "",
            "metadata": {},
        }
        statement = insert(CharacterRecord).values(values)
        statement = statement.on_conflict_do_nothing(index_elements=[CharacterRecord.character_id])
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

        persisted = await self.get_by_id(character_id)
        if persisted is None:
            raise RuntimeError("Character creation failed unexpectedly.")
        return persisted

    @staticmethod
    def _to_domain(record: CharacterRecord | None) -> Character | None:
        if record is None:
            return None

        try:
            visibility = CharacterVisibility(record.visibility)
        except ValueError:
            visibility = CharacterVisibility.PRIVATE

        metadata: dict[str, str] = {}
        if isinstance(record.payload_metadata, dict):
            metadata = {
                key: value
                for key, value in record.payload_metadata.items()
                if isinstance(key, str) and isinstance(value, str)
            }

        return Character(
            id=record.character_id,
            owner_id=record.owner_id,
            visibility=visibility,
            name=record.name,
            description=record.description,
            personality=record.personality,
            greeting=record.greeting,
            metadata=metadata,
        )
