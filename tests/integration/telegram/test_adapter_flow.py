from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.commands import HELP_MESSAGE
from rp_engine.core.memory.models import ConversationIdentity


@dataclass
class FakeUser:
    id: int


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
async def test_telegram_adapter_flow_calls_chat_service_and_replies() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="bot reply")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    message = FakeMessage(text="hello")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.send_message.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_private("42"),
        message="hello",
    )
    assert message.responses == ["bot reply"]


@pytest.mark.asyncio
async def test_telegram_adapter_ignores_non_text_messages() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    update = FakeUpdate(
        effective_message=FakeMessage(text=None),
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_command_is_handled_in_adapter() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    message = FakeMessage(text="/help")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == [HELP_MESSAGE]
    chat_service.send_message.assert_not_awaited()
    chat_service.continue_story.assert_not_awaited()
    chat_service.clear_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_continue_command_calls_continue_story() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(return_value="continued")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    message = FakeMessage(text="/continue")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=9),
        effective_chat=FakeChat(id=9, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.continue_story.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_private("9"),
    )
    chat_service.send_message.assert_not_awaited()
    assert message.responses == ["continued"]


@pytest.mark.asyncio
async def test_clear_command_calls_clear_conversation_and_confirms() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    message = FakeMessage(text="/clear")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=10),
        effective_chat=FakeChat(id=-100, type="group"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.clear_conversation.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_group("-100"),
    )
    assert message.responses == ["Conversation cleared."]


@pytest.mark.asyncio
async def test_unauthorized_user_gets_configured_message() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization({"123"}),
        unauthorized_message="beta closed",
    )

    message = FakeMessage(text="hello")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=999),
        effective_chat=FakeChat(id=999, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == ["beta closed"]
    chat_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_group_chat_ignores_normal_messages() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    message = FakeMessage(text="hello from group")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.send_message.assert_not_awaited()
    assert message.responses == []


@pytest.mark.asyncio
async def test_group_chat_supported_command_still_works() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(return_value="continued in group")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
    )

    message = FakeMessage(text="/continue")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.continue_story.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_group("-555"),
    )
    assert message.responses == ["continued in group"]
