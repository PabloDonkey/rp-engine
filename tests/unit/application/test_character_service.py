from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from rp_engine.application.services.character_service import CharacterService
from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.session.session import Session
from rp_engine.core.world.world import World

OWNER_ID = UUID("00000000-0000-0000-0000-000000000042")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000099")


class FakeCharacterStore:
    def __init__(self) -> None:
        self.items: dict[str, Character] = {}
        self.create_calls = 0

    async def get_by_id(self, character_id: str) -> Character | None:
        return self.items.get(character_id)

    async def find_by_name(self, name: str) -> Character | None:
        target = name.strip().lower()
        for value in self.items.values():
            if value.name.strip().lower() == target:
                return value
        return None

    async def create_minimal(
        self,
        *,
        character_id: str,
        owner_id: UUID,
        name: str,
        visibility: CharacterVisibility = CharacterVisibility.PRIVATE,
    ) -> Character:
        self.create_calls += 1
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
        self.items[character_id] = created
        return created

    async def find_owned_by_name(self, *, owner_id: UUID, name: str) -> Character | None:
        del owner_id
        return await self.find_by_name(name)

    async def save(self, character: Character) -> Character:
        self.items[character.id] = character
        return character


class FakeConversationStore:
    def __init__(self) -> None:
        self.messages: dict[str, list[ConversationMessage]] = {}

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        self.messages.setdefault(memory_key.value, []).append(message)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self.messages.get(memory_key.value, []))

    async def clear(self, memory_key: MemoryKey) -> None:
        self.messages.pop(memory_key.value, None)


class FakeWorldStore:
    async def get_by_id(self, world_id: str) -> World | None:
        return World(id=world_id, name="Default", description="Default world")

    async def create_default(self, *, world_id: str) -> World:
        return World(id=world_id, name="Default", description="Default world")


class FakeSessionStore:
    async def find_by_relationship(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None:
        del owner_kind
        del owner_id
        del character_id
        del world_id
        return None

    async def save(self, session: Session) -> Session:
        return session

    async def set_active_for_owner(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        del owner_kind
        del owner_id
        del session_id

    async def get_active_for_owner(self, *, owner_kind: str, owner_id: UUID) -> Session | None:
        del owner_kind
        del owner_id
        return None


@pytest.mark.asyncio
async def test_select_character_no_longer_creates_missing_character() -> None:
    character_store = FakeCharacterStore()
    service = CharacterService(
        character_store=character_store,
        conversation_store=FakeConversationStore(),
        world_store=FakeWorldStore(),
        session_store=FakeSessionStore(),
        default_world_id="default",
    )

    with pytest.raises(ValueError, match="Character not found"):
        await service.select_character_for_user(
            user_id=OWNER_ID,
            command=SelectCharacterCommand(character_name="Unknown"),
        )

    assert character_store.create_calls == 0


@pytest.mark.asyncio
async def test_describe_session_entry_uses_greeting_as_first_turn() -> None:
    character_store = FakeCharacterStore()
    conversation_store = FakeConversationStore()
    character_store.items["belzebuth"] = Character(
        id="belzebuth",
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Ancient dragon mage",
        personality="Wise and ruthless",
        greeting="Who dares wake me?",
        metadata={"scenario": "Ruined temple"},
    )
    service = CharacterService(
        character_store=character_store,
        conversation_store=conversation_store,
        world_store=FakeWorldStore(),
        session_store=FakeSessionStore(),
        default_world_id="default",
    )
    session = Session(
        id=SESSION_ID,
        owner_kind="user",
        owner_id=OWNER_ID,
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )

    entry = await service.describe_session_entry(session=session)
    assert entry == "Who dares wake me?"

    key = ConversationIdentity.for_session(str(SESSION_ID)).to_memory_key().value
    history = conversation_store.messages[key]
    assert len(history) == 1
    assert history[0].role == ConversationRole.CHARACTER
    assert history[0].content == "Who dares wake me?"


@pytest.mark.asyncio
async def test_describe_session_entry_returns_inferred_resume_without_greeting() -> None:
    character_store = FakeCharacterStore()
    conversation_store = FakeConversationStore()
    character_store.items["belzebuth"] = Character(
        id="belzebuth",
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Ancient dragon mage",
        personality="Wise and ruthless",
        greeting="Who dares wake me?",
        metadata={"scenario": "Ruined temple"},
    )
    service = CharacterService(
        character_store=character_store,
        conversation_store=conversation_store,
        world_store=FakeWorldStore(),
        session_store=FakeSessionStore(),
        default_world_id="default",
    )
    session = Session(
        id=SESSION_ID,
        owner_kind="user",
        owner_id=OWNER_ID,
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    memory_key = ConversationIdentity.for_session(str(SESSION_ID)).to_memory_key()

    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.CHARACTER, content="Who dares wake me?"),
    )
    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.USER, content="Tell me your name."),
    )
    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.CHARACTER, content="I am Belzebuth."),
    )
    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.USER, content="Where are we?"),
    )
    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.CHARACTER, content="Inside the ruined temple."),
    )
    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.USER, content="What do you seek?"),
    )

    entry = await service.describe_session_entry(session=session)

    assert entry is not None
    assert entry.startswith("Inferred resume from recent turns:")
    assert "User intent recently focused on:" in entry
    assert "Character recently established:" in entry
    assert "Who dares wake me?" not in entry
    assert "Where are we?" in entry
    assert "Inside the ruined temple." in entry
