from unittest.mock import AsyncMock

import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.memory.models import MemoryKey


@pytest.mark.asyncio
async def test_orchestrator_calls_provider_with_conversation() -> None:
    provider = AsyncMock()
    provider.generate_response = AsyncMock(return_value="generated")
    orchestrator = RPOrchestrator(llm_provider=provider)
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
        )
    )

    assert result == "generated"
    provider.generate_response.assert_awaited_once_with(conversation)


@pytest.mark.asyncio
async def test_orchestrator_propagates_provider_errors() -> None:
    provider = AsyncMock()
    provider.generate_response = AsyncMock(side_effect=RuntimeError("provider down"))
    orchestrator = RPOrchestrator(llm_provider=provider)
    conversation = Conversation(
        messages=[ConversationMessage(role=ConversationRole.USER, content="hello")]
    )

    with pytest.raises(RuntimeError, match="provider down"):
        await orchestrator.generate_reply(
            GenerationRequest(
                memory_key=MemoryKey("session_abc"),
                conversation=conversation,
            )
        )
