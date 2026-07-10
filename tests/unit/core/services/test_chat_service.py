from unittest.mock import AsyncMock

import pytest

from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_chat_service_builds_request_and_calls_orchestrator() -> None:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value="scene response")
    service = ChatService(orchestrator=orchestrator)

    response = await service.handle_user_message(user_id="user-1", message="  hello there  ")

    assert response == "scene response"
    orchestrator.generate_reply.assert_awaited_once_with(
        GenerationRequest(user_id="user-1", message="hello there")
    )


@pytest.mark.asyncio
async def test_chat_service_rejects_empty_message() -> None:
    orchestrator = AsyncMock()
    service = ChatService(orchestrator=orchestrator)

    with pytest.raises(ValueError, match="Message must not be empty"):
        await service.handle_user_message(user_id="user-1", message="   ")

    orchestrator.generate_reply.assert_not_awaited()
