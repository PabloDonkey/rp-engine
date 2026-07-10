from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter


@dataclass
class FakeUser:
    id: int


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


@pytest.mark.asyncio
async def test_telegram_adapter_flow_calls_chat_service_and_replies() -> None:
    chat_service = AsyncMock()
    chat_service.handle_user_message = AsyncMock(return_value="bot reply")
    adapter = TelegramAdapter(chat_service=chat_service)

    message = FakeMessage(text="hello")
    update = FakeUpdate(effective_message=message, effective_user=FakeUser(id=42))

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.handle_user_message.assert_awaited_once_with(user_id="42", message="hello")
    assert message.responses == ["bot reply"]


@pytest.mark.asyncio
async def test_telegram_adapter_ignores_non_text_messages() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(chat_service=chat_service)

    update = FakeUpdate(effective_message=FakeMessage(text=None), effective_user=FakeUser(id=42))

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.handle_user_message.assert_not_awaited()
