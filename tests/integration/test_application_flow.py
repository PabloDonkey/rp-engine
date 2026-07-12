from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.core.engine.models import PromptPayload
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.memory.dump_everything_strategy import DumpEverythingStrategy
from rp_engine.core.memory.models import ConversationMessage, MemoryKey
from rp_engine.core.services.chat_service import ChatService
from rp_engine.core.services.commands import SelectCharacterCommand
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User

FIXED_USER_ID = UUID("00000000-0000-0000-0000-000000000042")


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


class FakeCharacterService:
    async def ensure_active_session(self, *, user_id: UUID) -> Session:
        del user_id
        return Session.create(user_id=FIXED_USER_ID, character_id="default", world_id="default")

    async def select_character(self, *, user_id: UUID, command: SelectCharacterCommand) -> Session:
        del user_id
        return Session.create(
            user_id=FIXED_USER_ID,
            character_id=command.character_name.lower(),
            world_id="default",
        )


class FakeLLMProvider:
    def __init__(self) -> None:
        self.prompts: list[PromptPayload] = []

    async def generate_response(self, prompt: PromptPayload) -> str:
        self.prompts.append(prompt)
        return f"echo:{prompt.user_message}"


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[ConversationMessage]] = {}

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        self._messages.setdefault(memory_key.value, []).append(message)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self._messages.get(memory_key.value, []))

    async def clear(self, memory_key: MemoryKey) -> None:
        self._messages.pop(memory_key.value, None)


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
    orchestrator = RPOrchestrator(llm_provider=provider, system_prompt="smoke-system")
    chat_service = ChatService(
        orchestrator=orchestrator,
        conversation_store=InMemoryConversationStore(),
        memory_strategy=DumpEverythingStrategy(),
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        character_service=FakeCharacterService(),
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

    assert provider.prompts == [
        PromptPayload(system_prompt="smoke-system", user_message="hello smoke test")
    ]
    assert message.responses == ["echo:hello smoke test"]


@pytest.mark.asyncio
async def test_continue_command_is_not_sent_or_saved_as_literal_command() -> None:
    provider = FakeLLMProvider()
    store = InMemoryConversationStore()
    orchestrator = RPOrchestrator(llm_provider=provider, system_prompt="smoke-system")
    chat_service = ChatService(
        orchestrator=orchestrator,
        conversation_store=store,
        memory_strategy=DumpEverythingStrategy(),
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        character_service=FakeCharacterService(),
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

    assert provider.prompts
    assert "/continue" not in provider.prompts[0].user_message

    keys = list(store._messages.keys())
    assert keys
    saved_messages = await store.load_messages(MemoryKey(keys[0]))
    assert saved_messages
    assert all(message.role == "assistant" for message in saved_messages)
    assert all("/continue" not in message.content for message in saved_messages)
