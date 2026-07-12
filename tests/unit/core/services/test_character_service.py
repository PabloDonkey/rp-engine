from uuid import UUID

import pytest

from rp_engine.core.character.character import Character
from rp_engine.core.services.character_service import CharacterService
from rp_engine.core.services.commands import SelectCharacterCommand
from rp_engine.core.session.session import Session
from rp_engine.core.world.world import World


class InMemoryCharacterStore:
    def __init__(self) -> None:
        self._items: dict[str, Character] = {}

    async def get_by_id(self, character_id: str) -> Character | None:
        return self._items.get(character_id)

    async def find_by_name(self, name: str) -> Character | None:
        target = name.strip().lower()
        for character in self._items.values():
            if character.name.lower() == target:
                return character
        return None

    async def create_minimal(self, *, character_id: str, name: str) -> Character:
        created = Character(
            id=character_id,
            name=name,
            description=f"Character profile for {name}.",
            personality="Open-ended roleplay persona.",
            greeting="",
            metadata={},
        )
        self._items[character_id] = created
        return created


class InMemoryWorldStore:
    def __init__(self) -> None:
        self._items: dict[str, World] = {}

    async def get_by_id(self, world_id: str) -> World | None:
        return self._items.get(world_id)

    async def create_default(self, *, world_id: str) -> World:
        world = World(
            id=world_id,
            name="Default World",
            description="A flexible world with minimal predefined constraints.",
            rules=(),
            metadata={},
        )
        self._items[world_id] = world
        return world


class InMemorySessionStore:
    def __init__(self) -> None:
        self._items: dict[UUID, Session] = {}
        self._active_by_user: dict[UUID, UUID] = {}

    async def get_by_id(self, session_id: UUID) -> Session | None:
        return self._items.get(session_id)

    async def find_by_relationship(
        self,
        *,
        user_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None:
        for session in self._items.values():
            if (
                session.user_id == user_id
                and session.character_id == character_id
                and session.world_id == world_id
            ):
                return session
        return None

    async def save(self, session: Session) -> Session:
        self._items[session.id] = session
        return session

    async def set_active_for_user(self, *, user_id: UUID, session_id: UUID) -> None:
        self._active_by_user[user_id] = session_id

    async def get_active_for_user(self, *, user_id: UUID) -> Session | None:
        active_id = self._active_by_user.get(user_id)
        if active_id is None:
            return None
        return self._items.get(active_id)


@pytest.mark.asyncio
async def test_select_character_reuses_existing_session() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    character_store = InMemoryCharacterStore()
    world_store = InMemoryWorldStore()
    session_store = InMemorySessionStore()
    service = CharacterService(
        character_store=character_store,
        world_store=world_store,
        session_store=session_store,
        default_world_id="default",
    )

    first = await service.select_character(
        user_id=user_id,
        command=SelectCharacterCommand(character_name="Belzebuth"),
    )
    second = await service.select_character(
        user_id=user_id,
        command=SelectCharacterCommand(character_name="belzebuth"),
    )

    assert second.id == first.id


@pytest.mark.asyncio
async def test_ensure_active_session_creates_default_context() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000002")
    service = CharacterService(
        character_store=InMemoryCharacterStore(),
        world_store=InMemoryWorldStore(),
        session_store=InMemorySessionStore(),
        default_world_id="default",
    )

    session = await service.ensure_active_session(user_id=user_id)

    assert session.user_id == user_id
    assert session.character_id == "default"
    assert session.world_id == "default"
