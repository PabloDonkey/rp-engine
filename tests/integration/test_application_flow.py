from dataclasses import dataclass
from typing import Any, cast

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
from rp_engine.core.engine.models import PromptPayload
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.services.chat_service import ChatService


class FakeLLMProvider:
    def __init__(self) -> None:
        self.prompts: list[PromptPayload] = []

    async def generate_response(self, prompt: PromptPayload) -> str:
        self.prompts.append(prompt)
        return f"echo:{prompt.user_message}"


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
async def test_application_smoke_flow_without_external_services() -> None:
    provider = FakeLLMProvider()
    orchestrator = RPOrchestrator(llm_provider=provider, system_prompt="smoke-system")
    chat_service = ChatService(orchestrator=orchestrator)
    adapter = TelegramAdapter(chat_service=chat_service)

    message = FakeMessage(text="hello smoke test")
    update = FakeUpdate(effective_message=message, effective_user=FakeUser(id=7))

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert provider.prompts == [
        PromptPayload(system_prompt="smoke-system", user_message="hello smoke test")
    ]
    assert message.responses == ["echo:hello smoke test"]
