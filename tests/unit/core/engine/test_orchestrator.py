from unittest.mock import AsyncMock

import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.core.memory.models import MemoryKey


@pytest.mark.asyncio
async def test_orchestrator_calls_provider_with_conversation() -> None:
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value=LLMResponse(content="generated"))
    orchestrator = RPOrchestrator(llm_provider=provider)
    generation_settings = GenerationSettings(temperature=0.4, max_tokens=256)
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="system prompt"),
            ConversationMessage(role=ConversationRole.USER, content="continue the scene"),
        ]
    )

    result = await orchestrator.generate_reply(
        GenerationRequest(
            memory_key=MemoryKey("session_abc"),
            conversation=conversation,
            settings=generation_settings,
        )
    )

    assert result == LLMResponse(content="generated")
    provider.generate.assert_awaited_once_with(conversation, generation_settings)


@pytest.mark.asyncio
async def test_orchestrator_propagates_provider_errors() -> None:
    provider = AsyncMock()
    provider.generate = AsyncMock(side_effect=RuntimeError("provider down"))
    orchestrator = RPOrchestrator(llm_provider=provider)
    generation_settings = GenerationSettings()
    conversation = Conversation(
        messages=[ConversationMessage(role=ConversationRole.USER, content="hello")]
    )

    with pytest.raises(RuntimeError, match="provider down"):
        await orchestrator.generate_reply(
            GenerationRequest(
                memory_key=MemoryKey("session_abc"),
                conversation=conversation,
                settings=generation_settings,
            )
        )
