from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.application.services.chat_service import ChatService
from rp_engine.application.services.playthrough_service import PlaythroughStart
from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.group.group import Group
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.core.memory.dump_everything_strategy import DumpEverythingStrategy
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

FIXED_USER_ID = UUID("00000000-0000-0000-0000-000000000042")
FIXED_GROUP_ID = UUID("00000000-0000-0000-0000-000000000333")
FIXED_SESSION_ID = UUID("00000000-0000-0000-0000-000000000999")
DEFAULT_DEFINITION_ID = "def-default"
ROLE = "character"


def _default_character() -> Character:
    return Character(
        id="default",
        name="Belzebuth",
        description="{{char}} is a dragon companion of {{user}}.",
        personality="Protective and witty.",
        greeting="Welcome back, {{user}}.",
    )


def _default_world() -> World:
    return World(
        id="default",
        name="Main World",
        description="{{user}} explores a realm with {{char}}.",
        rules=("Stay in character.",),
    )


def _default_definition() -> ScenarioDefinition:
    return ScenarioDefinition(
        id=DEFAULT_DEFINITION_ID,
        owner_id=FIXED_USER_ID,
        name="Belzebuth",
        description="",
        world=_default_world(),
        characters={ROLE: _default_character()},
    )


def _fixed_session(*, owner_kind: str = "user", owner_id: UUID = FIXED_USER_ID) -> ScenarioSession:
    return ScenarioSession(
        id=FIXED_SESSION_ID,
        scenario_definition_id=DEFAULT_DEFINITION_ID,
        owner_kind=owner_kind,  # type: ignore[arg-type]
        owner_id=owner_id,
        active_participants={ROLE: "default"},
        created_at=datetime.now(UTC),
    )


class FakeIdentityResolver:
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User:
        del provider
        del external_id
        del metadata
        return User(id=FIXED_USER_ID, display_name=display_name)


class FakePlaythroughService:
    """Reports a fixed active playthrough so plain messages reach the chat service."""

    def __init__(self, *, active: ScenarioSession | None = None) -> None:
        self._active = active if active is not None else _fixed_session()

    def list_scenarios(self) -> list[ScenarioDefinition]:
        return [_default_definition()]

    async def get_active(self, *, owner_kind: str, owner_id: UUID) -> ScenarioSession | None:
        del owner_id
        if owner_kind == "group":
            return _fixed_session(owner_kind="group", owner_id=FIXED_GROUP_ID)
        return self._active

    async def start(
        self, *, owner_kind: str, owner_id: UUID, scenario_id: str
    ) -> PlaythroughStart | None:
        del owner_id, scenario_id
        session = _fixed_session(owner_kind=owner_kind, owner_id=FIXED_USER_ID)
        return PlaythroughStart(
            session=session, scenario=_default_definition(), opening="Opening."
        )

    async def restart(self, *, owner_kind: str, owner_id: UUID) -> PlaythroughStart | None:
        del owner_kind, owner_id
        return PlaythroughStart(
            session=_fixed_session(), scenario=_default_definition(), opening="Opening."
        )

    async def resume_text(self, *, session: ScenarioSession) -> str | None:
        del session
        return None


class FakeGroupIdentityResolver:
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group:
        del provider
        del external_id
        del metadata
        return Group(id=FIXED_GROUP_ID, display_name=display_name)


class FakeLLMProvider:
    def __init__(self) -> None:
        self.conversations: list[Conversation] = []
        self.settings: list[GenerationSettings] = []

    async def generate(
        self,
        conversation: Conversation,
        settings: GenerationSettings,
    ) -> LLMResponse:
        self.conversations.append(conversation)
        self.settings.append(settings)
        last_user = next(
            (
                message.content
                for message in reversed(conversation.messages)
                if message.role == ConversationRole.USER
            ),
            "",
        )
        return LLMResponse(content=f"echo:{last_user}", finish_reason="stop")


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[ConversationMessage]] = {}

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        self._messages.setdefault(memory_key.value, []).append(message)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self._messages.get(memory_key.value, []))

    async def clear(self, memory_key: MemoryKey) -> None:
        self._messages.pop(memory_key.value, None)


class FakeScenarioSessionStore:
    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        if session_id != FIXED_SESSION_ID:
            return None
        return _fixed_session()

    async def find_by_owner(self, owner_kind: str, owner_id: UUID) -> list[ScenarioSession]:
        del owner_kind
        del owner_id
        return []

    async def find_by_definition(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        del owner_kind
        del owner_id
        del scenario_definition_id
        return None

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        return session

    async def delete(self, session_id: UUID) -> None:
        del session_id

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

    async def get_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID
    ) -> ScenarioSession | None:
        del owner_kind
        del owner_id
        return None


class FakeScenarioDefinitionStore:
    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        if scenario_id != DEFAULT_DEFINITION_ID:
            return None
        return _default_definition()

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        del owner_id
        return []

    async def save(self, scenario: ScenarioDefinition) -> None:
        del scenario

    async def delete(self, scenario_id: str) -> None:
        del scenario_id


class FakeUserStore:
    async def get_user_by_identity(self, *, provider: str, external_id: str) -> User | None:
        del provider
        del external_id
        return None

    async def create_user_with_identity(
        self,
        *,
        display_name: str,
        identity: UserIdentity,
    ) -> User:
        del identity
        return User(id=FIXED_USER_ID, display_name=display_name)

    async def get_by_id(self, user_id: UUID) -> User | None:
        if user_id != FIXED_USER_ID:
            return None
        return User(id=FIXED_USER_ID, display_name="Pablo")


class FakeGroupStore:
    async def get_group_by_identity(self, *, provider: str, external_id: str) -> Group | None:
        del provider
        del external_id
        return None

    async def create_group_with_identity(self, *, display_name: str, identity: Any) -> Group:
        del identity
        return Group(id=FIXED_GROUP_ID, display_name=display_name)

    async def get_by_id(self, group_id: UUID) -> Group | None:
        if group_id != FIXED_GROUP_ID:
            return None
        return Group(id=FIXED_GROUP_ID, display_name="Test Group")


@dataclass
class FakeUser:
    id: int
    username: str | None = None
    full_name: str = "Test User"
    first_name: str | None = "Test"
    last_name: str | None = "User"


@dataclass
class FakeChat:
    id: int
    type: str


class FakeMessage:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.responses: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.responses.append(text)


@dataclass
class FakeUpdate:
    effective_message: FakeMessage | None
    effective_user: FakeUser | None
    effective_chat: FakeChat | None


@pytest.mark.asyncio
async def test_application_smoke_flow_without_external_services() -> None:
    provider = FakeLLMProvider()
    orchestrator = RPOrchestrator(llm_provider=provider)
    chat_service = ChatService(
        orchestrator=orchestrator,
        conversation_store=InMemoryConversationStore(),
        memory_strategy=DumpEverythingStrategy(),
        user_identity_store=FakeUserStore(),
        group_identity_store=FakeGroupStore(),
        scenario_session_store=FakeScenarioSessionStore(),
        scenario_definition_store=FakeScenarioDefinitionStore(),
        generation_settings=GenerationSettings(),
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="hello smoke test")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=7),
        effective_chat=FakeChat(id=7, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert provider.conversations
    assert provider.conversations[0].messages[-1].content == "hello smoke test"
    assert message.responses == ["echo:hello smoke test"]


@pytest.mark.asyncio
async def test_continue_command_is_not_saved_as_literal_command() -> None:
    provider = FakeLLMProvider()
    store = InMemoryConversationStore()
    orchestrator = RPOrchestrator(llm_provider=provider)
    chat_service = ChatService(
        orchestrator=orchestrator,
        conversation_store=store,
        memory_strategy=DumpEverythingStrategy(),
        user_identity_store=FakeUserStore(),
        group_identity_store=FakeGroupStore(),
        scenario_session_store=FakeScenarioSessionStore(),
        scenario_definition_store=FakeScenarioDefinitionStore(),
        generation_settings=GenerationSettings(),
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    update = FakeUpdate(
        effective_message=FakeMessage(text="/continue"),
        effective_user=FakeUser(id=7),
        effective_chat=FakeChat(id=7, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert provider.conversations
    assert "/continue" not in provider.conversations[0].messages[-1].content

    keys = list(store._messages.keys())
    assert keys
    saved_messages = await store.load_messages(MemoryKey(keys[0]))
    assert saved_messages
    assert all(message.role == ConversationRole.CHARACTER for message in saved_messages)
    assert all("/continue" not in message.content for message in saved_messages)
