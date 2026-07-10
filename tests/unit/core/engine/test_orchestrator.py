from unittest.mock import AsyncMock

import pytest

from rp_engine.core.engine.models import GenerationRequest, PromptPayload
from rp_engine.core.engine.orchestrator import RPOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_builds_prompt_and_calls_provider() -> None:
    provider = AsyncMock()
    provider.generate_response = AsyncMock(return_value="generated")
    orchestrator = RPOrchestrator(llm_provider=provider, system_prompt="system prompt")

    result = await orchestrator.generate_reply(
        GenerationRequest(user_id="user-1", message="continue the scene")
    )

    assert result == "generated"
    provider.generate_response.assert_awaited_once_with(
        PromptPayload(system_prompt="system prompt", user_message="continue the scene")
    )
