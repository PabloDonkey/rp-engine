from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from rp_engine.application.services.character_service import (
    SWITCH_CONTEXT_FROM_CHARACTER_ID,
    SWITCH_CONTEXT_SUMMARY,
    SWITCH_CONTEXT_TO_CHARACTER_ID,
    CharacterService,
)
from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.session.session import Session
from rp_engine.core.world.world import World

OWNER_ID = UUID("00000000-0000-0000-0000-000000000042")
ACTIVE_TORD_SESSION_ID = UUID("00000000-0000-0000-0000-000000000100")
BELZEBUTH_SESSION_ID = UUID("00000000-0000-0000-0000-000000000101")


class FakeConversationSummarizer:
    def __init__(self, summary: str = "Transition summary") -> None:
        self.summary = summary
        self.calls: list[list[ConversationMessage]] = []
        self.raise_error = False

    async def summarize_recent_conversation(
        self,
        *,
        recent_messages: list[ConversationMessage],
    ) -> str:
        self.calls.append(list(recent_messages))
        if self.raise_error:
            raise RuntimeError("summary failed")
        return self.summary


class FakeCharacterStore:
    def __init__(self) -> None:
        self.items: dict[str, Character] = {}

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
    def __init__(self) -> None:
        self.sessions: dict[UUID, Session] = {}
        self.active: dict[tuple[str, UUID], UUID] = {}

    async def get_by_id(self, session_id: UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def find_by_relationship(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None:
        for session in self.sessions.values():
            if (
                session.owner_kind == owner_kind
                and session.owner_id == owner_id
                and session.character_id == character_id
                and session.world_id == world_id
            ):
                return session
        return None

    async def save(self, session: Session) -> Session:
        self.sessions[session.id] = session
        return session

    async def set_active_for_owner(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        self.active[(owner_kind, owner_id)] = session_id

    async def get_active_for_owner(self, *, owner_kind: str, owner_id: UUID) -> Session | None:
        session_id = self.active.get((owner_kind, owner_id))
        if session_id is None:
            return None
        return self.sessions.get(session_id)


def _character(*, character_id: str, name: str, greeting: str) -> Character:
    return Character(
        id=character_id,
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name=name,
        description=f"{name} description",
        personality=f"{name} personality",
        greeting=greeting,
        metadata={"first_message": greeting},
    )


def _service_with_fixtures() -> tuple[
    CharacterService,
    FakeCharacterStore,
    FakeConversationStore,
    FakeSessionStore,
    FakeConversationSummarizer,
]:
    character_store = FakeCharacterStore()
    conversation_store = FakeConversationStore()
    session_store = FakeSessionStore()
    summarizer = FakeConversationSummarizer(
        summary=(
            "The user and Tord were investigating an abandoned facility and found signs "
            "of hidden experiments. The user is cautious but wants to continue. The next "
            "step is deciding whether to enter the sealed lower wing."
        )
    )
    service = CharacterService(
        character_store=character_store,
        conversation_store=conversation_store,
        conversation_summarizer=summarizer,
        world_store=FakeWorldStore(),
        session_store=session_store,
        default_world_id="default",
    )
    return service, character_store, conversation_store, session_store, summarizer


@pytest.mark.asyncio
async def test_first_activation_returns_greeting_and_does_not_summarize() -> None:
    service, character_store, conversation_store, _session_store, summarizer = _service_with_fixtures()
    character_store.items["belzebuth"] = _character(
        character_id="belzebuth",
        name="Belzebuth",
        greeting="Who dares wake me?",
    )

    selection = await service.select_character_for_user(
        user_id=OWNER_ID,
        command=SelectCharacterCommand(character_name="Belzebuth"),
    )

    assert selection.status == "activated"
    assert len(summarizer.calls) == 0

    entry = await service.describe_session_entry(session=selection.session)
    assert entry == "Who dares wake me?"

    key = ConversationIdentity.for_session(str(selection.session.id)).to_memory_key().value
    history = conversation_store.messages[key]
    assert len(history) == 1
    assert history[0].role == ConversationRole.CHARACTER
    assert history[0].content == "Who dares wake me?"


@pytest.mark.asyncio
async def test_character_switch_summarizes_last_four_and_stores_switch_context() -> None:
    service, character_store, conversation_store, session_store, summarizer = _service_with_fixtures()
    character_store.items["tord"] = _character(character_id="tord", name="Tord", greeting="...")
    character_store.items["belzebuth"] = _character(
        character_id="belzebuth",
        name="Belzebuth",
        greeting="Who dares wake me?",
    )

    active_tord_session = Session(
        id=ACTIVE_TORD_SESSION_ID,
        owner_kind="user",
        owner_id=OWNER_ID,
        character_id="tord",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    target_belzebuth_session = Session(
        id=BELZEBUTH_SESSION_ID,
        owner_kind="user",
        owner_id=OWNER_ID,
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    await session_store.save(active_tord_session)
    await session_store.save(target_belzebuth_session)
    await session_store.set_active_for_owner(
        owner_kind="user",
        owner_id=OWNER_ID,
        session_id=active_tord_session.id,
    )

    memory_key = ConversationIdentity.for_session(str(active_tord_session.id)).to_memory_key()
    recent = [
        ConversationMessage(role=ConversationRole.USER, content="We found the facility map."),
        ConversationMessage(role=ConversationRole.CHARACTER, content="The lower floor is sealed."),
        ConversationMessage(role=ConversationRole.USER, content="Should we force the door?"),
        ConversationMessage(role=ConversationRole.CHARACTER, content="There might be alarms."),
    ]
    older = ConversationMessage(role=ConversationRole.USER, content="Earlier unrelated turn")
    await conversation_store.save_message(memory_key, older)
    for message in recent:
        await conversation_store.save_message(memory_key, message)

    selection = await service.select_character_for_user(
        user_id=OWNER_ID,
        command=SelectCharacterCommand(character_name="Belzebuth"),
    )

    assert selection.status == "switched"
    assert len(summarizer.calls) == 1
    assert summarizer.calls[0] == recent
    assert selection.session.metadata[SWITCH_CONTEXT_FROM_CHARACTER_ID] == "tord"
    assert selection.session.metadata[SWITCH_CONTEXT_TO_CHARACTER_ID] == "belzebuth"
    assert selection.session.metadata[SWITCH_CONTEXT_SUMMARY] == summarizer.summary


@pytest.mark.asyncio
async def test_same_character_selection_is_noop_without_summary_generation() -> None:
    service, character_store, _conversation_store, session_store, summarizer = _service_with_fixtures()
    character_store.items["belzebuth"] = _character(
        character_id="belzebuth",
        name="Belzebuth",
        greeting="Who dares wake me?",
    )

    existing = Session(
        id=BELZEBUTH_SESSION_ID,
        owner_kind="user",
        owner_id=OWNER_ID,
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    await session_store.save(existing)
    await session_store.set_active_for_owner(
        owner_kind="user",
        owner_id=OWNER_ID,
        session_id=existing.id,
    )

    selection = await service.select_character_for_user(
        user_id=OWNER_ID,
        command=SelectCharacterCommand(character_name="Belzebuth"),
    )

    assert selection.status == "already_active"
    assert selection.session.id == existing.id
    assert len(summarizer.calls) == 0


@pytest.mark.asyncio
async def test_switch_continues_when_summarization_fails_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    service, character_store, conversation_store, session_store, summarizer = _service_with_fixtures()
    summarizer.raise_error = True
    character_store.items["tord"] = _character(character_id="tord", name="Tord", greeting="...")
    character_store.items["belzebuth"] = _character(
        character_id="belzebuth",
        name="Belzebuth",
        greeting="Who dares wake me?",
    )

    active_tord_session = Session(
        id=ACTIVE_TORD_SESSION_ID,
        owner_kind="user",
        owner_id=OWNER_ID,
        character_id="tord",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    await session_store.save(active_tord_session)
    await session_store.set_active_for_owner(
        owner_kind="user",
        owner_id=OWNER_ID,
        session_id=active_tord_session.id,
    )
    memory_key = ConversationIdentity.for_session(str(active_tord_session.id)).to_memory_key()
    await conversation_store.save_message(
        memory_key,
        ConversationMessage(role=ConversationRole.USER, content="Do we enter now?"),
    )

    selection = await service.select_character_for_user(
        user_id=OWNER_ID,
        command=SelectCharacterCommand(character_name="Belzebuth"),
    )

    assert selection.status == "switched"
    assert len(summarizer.calls) == 1
    assert SWITCH_CONTEXT_SUMMARY not in selection.session.metadata
    assert "Failed to generate character switch summary" in caplog.text
