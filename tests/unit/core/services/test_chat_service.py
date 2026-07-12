from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID

import pytest

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.services.chat_service import ChatService
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")
USER_ID = UUID("00000000-0000-0000-0000-000000000042")


@pytest.fixture
def session_context() -> tuple[Session, User, Character, World]:
    session = Session(
        id=SESSION_ID,
        user_id=USER_ID,
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    user = User(id=USER_ID, display_name="Pablo")
    character = Character(
        id="belzebuth",
        name="Belzebuth",
        description="{{char}} is a dragon companion of {{user}}.",
        personality="Protective and witty.",
        greeting="Welcome back, {{user}}.",
    )
    world = World(
        id="default",
        name="Main World",
        description="{{user}} explores a realm with {{char}}.",
        rules=("Stay in character.",),
    )
    return session, user, character, world


def _build_service(
    *,
    session_context: tuple[Session, User, Character, World],
) -> tuple[ChatService, AsyncMock, AsyncMock]:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value="scene response")
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[ConversationMessage(role=ConversationRole.USER, content="previous")]
    )
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = [
        ConversationMessage(role=ConversationRole.USER, content="previous")
    ]

    session, user, character, world = session_context

    session_store = AsyncMock()
    session_store.get_by_id = AsyncMock(return_value=session)

    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)

    character_store = AsyncMock()
    character_store.get_by_id = AsyncMock(return_value=character)

    world_store = AsyncMock()
    world_store.get_by_id = AsyncMock(return_value=world)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
    )
    return service, orchestrator, conversation_store


@pytest.mark.asyncio
async def test_chat_service_builds_conversation_and_calls_orchestrator(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, conversation_store = _build_service(session_context=session_context)

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="  hello there  ",
    )

    assert response == "scene response"
    request = orchestrator.generate_reply.await_args.args[0]
    assert request == GenerationRequest(
        memory_key=MemoryKey(f"session_{SESSION_ID}"),
        conversation=request.conversation,
    )

    assert isinstance(request.conversation, Conversation)
    assert request.conversation.messages[-1] == ConversationMessage(
        role=ConversationRole.USER,
        content="hello there",
        metadata={},
    )
    assert "{{char}}" not in "\n".join(message.content for message in request.conversation.messages)
    assert "{{user}}" not in "\n".join(message.content for message in request.conversation.messages)

    conversation_store.save_message.assert_has_awaits(
        [
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(
                    role=ConversationRole.USER,
                    content="hello there",
                    metadata={},
                ),
            ),
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(
                    role=ConversationRole.CHARACTER,
                    content="scene response",
                    metadata={},
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chat_service_rejects_empty_message(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, _ = _build_service(session_context=session_context)

    with pytest.raises(ValueError, match="Message must not be empty"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="   ",
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_requires_session_identity(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, _ = _build_service(session_context=session_context)

    with pytest.raises(ValueError, match="session-scoped"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_private("user-1"),
            message="hello",
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_continue_saves_character_message(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, conversation_store = _build_service(session_context=session_context)
    orchestrator.generate_reply = AsyncMock(return_value="continued scene")

    response = await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    assert response == "continued scene"
    conversation_store.save_message.assert_awaited_with(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content="continued scene",
            metadata={},
        ),
    )


@pytest.mark.asyncio
async def test_chat_service_clear_conversation_uses_store_clear() -> None:
    orchestrator = AsyncMock()
    conversation_store = AsyncMock()
    memory_strategy = Mock()
    session_store = AsyncMock()
    user_store = AsyncMock()
    character_store = AsyncMock()
    world_store = AsyncMock()

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
    )

    await service.clear_conversation(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    conversation_store.clear.assert_awaited_once_with(MemoryKey(f"session_{SESSION_ID}"))


@pytest.mark.asyncio
async def test_chat_service_persists_user_metadata(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, _, conversation_store = _build_service(session_context=session_context)

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I open the door",
        user_id="123456",
        username="alice",
        display_name="Alice",
    )

    first_saved = conversation_store.save_message.await_args_list[0]
    assert first_saved == call(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.USER,
            content="I open the door",
            metadata={
                "user_id": "123456",
                "username": "alice",
                "display_name": "Alice",
            },
        ),
    )
