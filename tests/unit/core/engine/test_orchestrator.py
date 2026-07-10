from unittest.mock import AsyncMock

import pytest

from rp_engine.core.engine.models import GenerationRequest, PromptPayload
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.memory.models import ConversationMessage, MemoryKey


@pytest.mark.asyncio
async def test_orchestrator_builds_prompt_and_calls_provider() -> None:
    provider = AsyncMock()
    provider.generate_response = AsyncMock(return_value="generated")
    orchestrator = RPOrchestrator(llm_provider=provider, system_prompt="system prompt")

    result = await orchestrator.generate_reply(
        GenerationRequest(
            memory_key=MemoryKey("user_user-1"),
            context_messages=[
                ConversationMessage(role="user", content="I open the door"),
                ConversationMessage(role="assistant", content="It creaks loudly"),
            ],
            instruction="continue the scene",
        )
    )

    assert result == "generated"
    provider.generate_response.assert_awaited_once_with(
        PromptPayload(
            system_prompt="system prompt",
            user_message=(
                "Conversation history:\n"
                "User: I open the door\n"
                "Assistant: It creaks loudly\n\n"
                "Next input:\n"
                "continue the scene"
            ),
        )
    )


@pytest.mark.asyncio
async def test_orchestrator_uses_instruction_directly_when_no_context() -> None:
    provider = AsyncMock()
    provider.generate_response = AsyncMock(return_value="generated")
    orchestrator = RPOrchestrator(llm_provider=provider, system_prompt="system prompt")

    result = await orchestrator.generate_reply(
        GenerationRequest(
            memory_key=MemoryKey("user_user-1"),
            context_messages=[],
            instruction="continue the scene",
        )
    )

    assert result == "generated"
    provider.generate_response.assert_awaited_once_with(
        PromptPayload(system_prompt="system prompt", user_message="continue the scene")
    )
