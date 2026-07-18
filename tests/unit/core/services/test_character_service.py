from uuid import UUID

import pytest

from rp_engine.application.services.character_service import CharacterService
from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import MemoryKey
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

    async def create_minimal(
        self,
        *,
        character_id: str,
        owner_id: UUID,
        name: str,
        visibility: CharacterVisibility = CharacterVisibility.PRIVATE,
    ) -> Character:
        created = Character(
            id=character_id,
            owner_id=owner_id,
            visibility=visibility,
            name=name,
            description=f"Character profile for {name}.",
            personality="Open-ended roleplay persona.",
            greeting="",
            metadata={},
        )
        self._items[character_id] = created
        return created

    async def find_owned_by_name(self, *, owner_id: UUID, name: str) -> Character | None:
        target = name.strip().lower()
        for character in self._items.values():
            if character.owner_id == owner_id and character.name.lower() == target:
                return character
        return None

    async def save(self, character: Character) -> Character:
        self._items[character.id] = character
        return character


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
        owner_kind: str,
        owner_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None:
        for session in self._items.values():
            if (
                session.owner_kind == owner_kind
                and session.owner_id == owner_id
                and session.character_id == character_id
                and session.world_id == world_id
            ):
                return session
        return None

    async def save(self, session: Session) -> Session:
        self._items[session.id] = session
        return session

    async def set_active_for_owner(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        del owner_kind
        self._active_by_user[owner_id] = session_id

    async def get_active_for_owner(self, *, owner_kind: str, owner_id: UUID) -> Session | None:
        del owner_kind
        active_id = self._active_by_user.get(owner_id)
        if active_id is None:
            return None
        return self._items.get(active_id)


class FakeConversationStore:
    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        del memory_key
        del message

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        del memory_key
        return []

    async def clear(self, memory_key: MemoryKey) -> None:
        del memory_key


class FakeConversationSummarizer:
    async def summarize_recent_conversation(
        self,
        *,
        recent_messages: list[ConversationMessage],
    ) -> str:
        del recent_messages
        return ""


@pytest.mark.asyncio
async def test_select_character_reuses_existing_session() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    character_store = InMemoryCharacterStore()
    world_store = InMemoryWorldStore()
    session_store = InMemorySessionStore()
    service = CharacterService(
        character_store=character_store,
        conversation_store=FakeConversationStore(),
        conversation_summarizer=FakeConversationSummarizer(),
        world_store=world_store,
        session_store=session_store,
        default_world_id="default",
    )

    first = await service.select_character_for_user(
        user_id=user_id,
        command=SelectCharacterCommand(character_name="Belzebuth"),
    )
    second = await service.select_character_for_user(
        user_id=user_id,
        command=SelectCharacterCommand(character_name="belzebuth"),
    )

    assert second.session.id == first.session.id


@pytest.mark.asyncio
async def test_ensure_active_session_creates_default_context() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000002")
    service = CharacterService(
        character_store=InMemoryCharacterStore(),
        conversation_store=FakeConversationStore(),
        conversation_summarizer=FakeConversationSummarizer(),
        world_store=InMemoryWorldStore(),
        session_store=InMemorySessionStore(),
        default_world_id="default",
    )

    session = await service.ensure_active_session_for_user(user_id=user_id)

    assert session.owner_kind == "user"
    assert session.owner_id == user_id
    assert session.character_id == "default"
    assert session.world_id == "default"


@pytest.mark.asyncio
async def test_different_users_do_not_share_sessions() -> None:
    service = CharacterService(
        character_store=InMemoryCharacterStore(),
        conversation_store=FakeConversationStore(),
        conversation_summarizer=FakeConversationSummarizer(),
        world_store=InMemoryWorldStore(),
        session_store=InMemorySessionStore(),
        default_world_id="default",
    )
    user_a = UUID("00000000-0000-0000-0000-000000000101")
    user_b = UUID("00000000-0000-0000-0000-000000000102")

    session_a = await service.ensure_active_session_for_user(user_id=user_a)
    session_b = await service.ensure_active_session_for_user(user_id=user_b)

    assert session_a.id != session_b.id
    assert session_a.owner_kind == "user"
    assert session_b.owner_kind == "user"
    assert session_a.owner_id == user_a
    assert session_b.owner_id == user_b


@pytest.mark.asyncio
async def test_different_groups_do_not_share_sessions() -> None:
    service = CharacterService(
        character_store=InMemoryCharacterStore(),
        conversation_store=FakeConversationStore(),
        conversation_summarizer=FakeConversationSummarizer(),
        world_store=InMemoryWorldStore(),
        session_store=InMemorySessionStore(),
        default_world_id="default",
    )
    group_a = UUID("00000000-0000-0000-0000-000000000201")
    group_b = UUID("00000000-0000-0000-0000-000000000202")

    session_a = await service.ensure_active_session_for_group(
        group_id=group_a,
        actor_user_id=UUID("00000000-0000-0000-0000-000000000900"),
    )
    session_b = await service.ensure_active_session_for_group(
        group_id=group_b,
        actor_user_id=UUID("00000000-0000-0000-0000-000000000901"),
    )

    assert session_a.id != session_b.id
    assert session_a.owner_kind == "group"
    assert session_b.owner_kind == "group"
    assert session_a.owner_id == group_a
    assert session_b.owner_id == group_b


@pytest.mark.asyncio
async def test_private_character_owned_by_another_user_is_rejected() -> None:
    owner_user_id = UUID("00000000-0000-0000-0000-000000000301")
    requester_user_id = UUID("00000000-0000-0000-0000-000000000302")
    character_store = InMemoryCharacterStore()
    await character_store.save(
        Character(
        id="belzebuth",
        owner_id=owner_user_id,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Character profile for Belzebuth.",
        personality="Open-ended roleplay persona.",
        )
    )
    service = CharacterService(
        character_store=character_store,
        conversation_store=FakeConversationStore(),
        conversation_summarizer=FakeConversationSummarizer(),
        world_store=InMemoryWorldStore(),
        session_store=InMemorySessionStore(),
        default_world_id="default",
    )

    with pytest.raises(ValueError, match="private and belongs to another user"):
        await service.select_character_for_user(
            user_id=requester_user_id,
            command=SelectCharacterCommand(character_name="Belzebuth"),
        )
