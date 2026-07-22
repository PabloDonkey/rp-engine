from uuid import UUID

import pytest

from rp_engine.application.services.character_service import AUTO_ROLE, CharacterService
from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
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
        )
        self._items[world_id] = world
        return world


class InMemoryScenarioDefinitionStore:
    def __init__(self) -> None:
        self._items: dict[str, ScenarioDefinition] = {}

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        return self._items.get(scenario_id)

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        return [item for item in self._items.values() if item.owner_id == owner_id]

    async def save(self, scenario: ScenarioDefinition) -> None:
        self._items[scenario.id] = scenario

    async def delete(self, scenario_id: str) -> None:
        self._items.pop(scenario_id, None)


class InMemoryScenarioSessionStore:
    def __init__(self) -> None:
        self._items: dict[UUID, ScenarioSession] = {}
        self._active: dict[tuple[str, UUID], UUID] = {}

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        return self._items.get(session_id)

    async def find_by_owner(self, owner_kind: str, owner_id: UUID) -> list[ScenarioSession]:
        return [
            session
            for session in self._items.values()
            if session.owner_kind == owner_kind and session.owner_id == owner_id
        ]

    async def find_by_definition(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        for session in self._items.values():
            if (
                session.owner_kind == owner_kind
                and session.owner_id == owner_id
                and session.scenario_definition_id == scenario_definition_id
            ):
                return session
        return None

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        self._items[session.id] = session
        return session

    async def delete(self, session_id: UUID) -> None:
        self._items.pop(session_id, None)

    async def set_active_for_owner(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        self._active[(owner_kind, owner_id)] = session_id

    async def get_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID
    ) -> ScenarioSession | None:
        active_id = self._active.get((owner_kind, owner_id))
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


def _build_service(
    *,
    character_store: InMemoryCharacterStore | None = None,
) -> CharacterService:
    return CharacterService(
        character_store=character_store or InMemoryCharacterStore(),
        conversation_store=FakeConversationStore(),
        conversation_summarizer=FakeConversationSummarizer(),
        world_store=InMemoryWorldStore(),
        scenario_definition_store=InMemoryScenarioDefinitionStore(),
        scenario_session_store=InMemoryScenarioSessionStore(),
        default_world_id="default",
    )


@pytest.mark.asyncio
async def test_select_character_reuses_existing_session() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    character_store = InMemoryCharacterStore()
    await character_store.save(
        Character(
            id="belzebuth",
            owner_id=user_id,
            visibility=CharacterVisibility.PRIVATE,
            name="Belzebuth",
            description="Belzebuth description",
            personality="Bold",
        )
    )
    service = _build_service(character_store=character_store)

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
    service = _build_service()

    session = await service.ensure_active_session_for_user(user_id=user_id)

    assert session.owner_kind == "user"
    assert session.owner_id == user_id
    assert session.active_participants[AUTO_ROLE] == "default"


@pytest.mark.asyncio
async def test_different_users_do_not_share_sessions() -> None:
    service = _build_service()
    user_a = UUID("00000000-0000-0000-0000-000000000101")
    user_b = UUID("00000000-0000-0000-0000-000000000102")

    session_a = await service.ensure_active_session_for_user(user_id=user_a)
    session_b = await service.ensure_active_session_for_user(user_id=user_b)

    assert session_a.id != session_b.id
    assert session_a.owner_id == user_a
    assert session_b.owner_id == user_b


@pytest.mark.asyncio
async def test_different_groups_do_not_share_sessions() -> None:
    service = _build_service()
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
    service = _build_service(character_store=character_store)

    with pytest.raises(ValueError, match="private and belongs to another user"):
        await service.select_character_for_user(
            user_id=requester_user_id,
            command=SelectCharacterCommand(character_name="Belzebuth"),
        )
