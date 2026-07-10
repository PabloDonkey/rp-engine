from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
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
    chat_service.handle_user_message = AsyncMock(return_value="bot reply")
    adapter = TelegramAdapter(chat_service=chat_service)

    message = FakeMessage(text="hello")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.handle_user_message.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_private("42"),
        message="hello",
    )
    assert message.responses == ["bot reply"]


@pytest.mark.asyncio
async def test_telegram_adapter_ignores_non_text_messages() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(chat_service=chat_service)

    update = FakeUpdate(
        effective_message=FakeMessage(text=None),
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.handle_user_message.assert_not_awaited()
