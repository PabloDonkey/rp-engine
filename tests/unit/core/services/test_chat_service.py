from unittest.mock import AsyncMock, Mock, call

import pytest

from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.memory.models import ConversationIdentity, ConversationMessage, MemoryKey
from rp_engine.core.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_chat_service_builds_request_and_calls_orchestrator() -> None:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value="scene response")
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[ConversationMessage(role="user", content="previous")]
    )
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = [
        ConversationMessage(role="user", content="previous")
    ]

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
    )

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_private("user-1"),
        message="  hello there  ",
    )

    assert response == "scene response"
    orchestrator.generate_reply.assert_awaited_once_with(
        GenerationRequest(
            memory_key=MemoryKey("user_user-1"),
            context_messages=[ConversationMessage(role="user", content="previous")],
            instruction="hello there",
        )
    )
    conversation_store.save_message.assert_has_awaits(
        [
            call(
                MemoryKey("user_user-1"),
                ConversationMessage(role="user", content="hello there"),
            ),
            call(
                MemoryKey("user_user-1"),
                ConversationMessage(role="assistant", content="scene response"),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chat_service_rejects_empty_message() -> None:
    orchestrator = AsyncMock()
    conversation_store = AsyncMock()
    memory_strategy = Mock()
    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
    )

    with pytest.raises(ValueError, match="Message must not be empty"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_private("user-1"),
            message="   ",
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_continue_saves_only_assistant_message() -> None:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value="continued scene")
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[ConversationMessage(role="assistant", content="scene so far")]
    )
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = [
        ConversationMessage(role="assistant", content="scene so far")
    ]
    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
    )

    response = await service.continue_story(
        conversation_identity=ConversationIdentity.for_group("-98765"),
    )

    assert response == "continued scene"
    orchestrator.generate_reply.assert_awaited_once()
    saved_calls = conversation_store.save_message.await_args_list
    assert saved_calls == [
        call(
            MemoryKey("group_-98765"),
            ConversationMessage(role="assistant", content="continued scene"),
        )
    ]


@pytest.mark.asyncio
async def test_chat_service_clear_conversation_uses_store_clear() -> None:
    orchestrator = AsyncMock()
    conversation_store = AsyncMock()
    memory_strategy = Mock()
    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
    )

    await service.clear_conversation(
        conversation_identity=ConversationIdentity.for_private("user-9"),
    )

    conversation_store.clear.assert_awaited_once_with(MemoryKey("user_user-9"))
