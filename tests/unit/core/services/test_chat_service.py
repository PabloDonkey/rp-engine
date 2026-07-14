from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID

import pytest

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.group.group import Group
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.services.chat_service import ChatService
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")
USER_ID = UUID("00000000-0000-0000-0000-000000000042")
GROUP_ID = UUID("00000000-0000-0000-0000-000000000314")
GENERATION_SETTINGS = GenerationSettings(temperature=0.8, max_tokens=600, top_p=0.95)


@pytest.fixture
def session_context() -> tuple[Session, User, Character, World]:
    session = Session(
        id=SESSION_ID,
        owner_kind="user",
        owner_id=USER_ID,
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
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene response"))
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

    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    character_store = AsyncMock()
    character_store.get_by_id = AsyncMock(return_value=character)

    world_store = AsyncMock()
    world_store.get_by_id = AsyncMock(return_value=world)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
        generation_settings=GENERATION_SETTINGS,
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
        settings=GENERATION_SETTINGS,
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
async def test_chat_service_rejects_invalid_session_identity(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, _ = _build_service(session_context=session_context)

    with pytest.raises(ValueError, match="invalid session id"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session("not-a-uuid"),
            message="hello",
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_continue_saves_character_message(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, conversation_store = _build_service(session_context=session_context)
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="continued scene"))

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
async def test_chat_service_regenerate_replaces_last_character_message(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, conversation_store = _build_service(session_context=session_context)
    conversation_store.load_messages = AsyncMock(
        return_value=[
            ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
            ConversationMessage(role=ConversationRole.CHARACTER, content="old reply", metadata={}),
        ]
    )
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="new reply"))

    response = await service.regenerate_last_response(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    assert response == "new reply"
    conversation_store.clear.assert_awaited_once_with(MemoryKey(f"session_{SESSION_ID}"))
    conversation_store.save_message.assert_has_awaits(
        [
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
            ),
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(
                    role=ConversationRole.CHARACTER,
                    content="new reply",
                    metadata={},
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chat_service_regenerate_requires_latest_character_message(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, conversation_store = _build_service(session_context=session_context)
    conversation_store.load_messages = AsyncMock(
        return_value=[ConversationMessage(role=ConversationRole.USER, content="hello", metadata={})]
    )

    with pytest.raises(ValueError, match="Last message is not a character reply"):
        await service.regenerate_last_response(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_regenerate_can_run_multiple_times(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, conversation_store = _build_service(session_context=session_context)
    conversation_store.load_messages = AsyncMock(
        side_effect=[
            [
                ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
                ConversationMessage(
                    role=ConversationRole.CHARACTER,
                    content="old reply",
                    metadata={},
                ),
            ],
            [
                ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
                ConversationMessage(
                    role=ConversationRole.CHARACTER,
                    content="first regen",
                    metadata={},
                ),
            ],
        ]
    )
    orchestrator.generate_reply = AsyncMock(
        side_effect=[LLMResponse(content="first regen"), LLMResponse(content="second regen")]
    )

    first = await service.regenerate_last_response(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )
    second = await service.regenerate_last_response(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    assert first == "first regen"
    assert second == "second regen"
    assert orchestrator.generate_reply.await_count == 2


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
        group_identity_store=AsyncMock(),
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
        generation_settings=GENERATION_SETTINGS,
    )

    await service.clear_conversation(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    conversation_store.clear.assert_awaited_once_with(MemoryKey(f"session_{SESSION_ID}"))


@pytest.mark.asyncio
async def test_chat_service_uses_group_owner_as_template_user() -> None:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene response"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=[])
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = []

    group_session = Session(
        id=SESSION_ID,
        owner_kind="group",
        owner_id=GROUP_ID,
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    session_store = AsyncMock()
    session_store.get_by_id = AsyncMock(return_value=group_session)

    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=Group(id=GROUP_ID, display_name="Raid Party"))

    character_store = AsyncMock()
    character_store.get_by_id = AsyncMock(
        return_value=Character(
            id="belzebuth",
            name="Belzebuth",
            description="{{char}} guards {{user}}.",
            personality="Protective and witty.",
            greeting="Welcome back, {{user}}.",
        )
    )

    world_store = AsyncMock()
    world_store.get_by_id = AsyncMock(
        return_value=World(
            id="default",
            name="Main World",
            description="{{user}} explores a realm with {{char}}.",
            rules=("Stay in character.",),
        )
    )

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=AsyncMock(),
        group_identity_store=group_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
        generation_settings=GENERATION_SETTINGS,
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    request = orchestrator.generate_reply.await_args.args[0]
    serialized = "\n".join(message.content for message in request.conversation.messages)
    assert "Raid Party" in serialized


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


@pytest.mark.asyncio
async def test_chat_service_starts_and_stops_processing_feedback(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, _, _ = _build_service(session_context=session_context)
    feedback = AsyncMock()
    feedback.start = AsyncMock()
    feedback.update = AsyncMock()
    feedback.stop = AsyncMock()

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
        processing_feedback=feedback,
    )

    feedback.start.assert_awaited_once()
    feedback.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_service_stops_processing_feedback_when_generation_fails(
    session_context: tuple[Session, User, Character, World],
) -> None:
    service, orchestrator, _ = _build_service(session_context=session_context)
    orchestrator.generate_reply = AsyncMock(side_effect=RuntimeError("provider down"))
    feedback = AsyncMock()
    feedback.start = AsyncMock()
    feedback.update = AsyncMock()
    feedback.stop = AsyncMock()

    with pytest.raises(RuntimeError, match="provider down"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
            processing_feedback=feedback,
        )

    feedback.start.assert_awaited_once()
    feedback.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_service_writes_generation_trace_in_all_mode(
    session_context: tuple[Session, User, Character, World],
) -> None:
    session, user, character, world = session_context
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(
        return_value=LLMResponse(
            content="scene response",
            finish_reason="stop",
            metadata={
                "provider": "lmstudio",
                "model_name": "model-a",
                "usage_prompt_tokens": "12",
                "usage_completion_tokens": "6",
            },
        )
    )
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[ConversationMessage(role=ConversationRole.USER, content="previous")]
    )
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = [
        ConversationMessage(role=ConversationRole.USER, content="previous")
    ]
    session_store = AsyncMock()
    session_store.get_by_id = AsyncMock(return_value=session)
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)
    group_store = AsyncMock()
    character_store = AsyncMock()
    character_store.get_by_id = AsyncMock(return_value=character)
    world_store = AsyncMock()
    world_store.get_by_id = AsyncMock(return_value=world)
    trace_store = AsyncMock()

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
        generation_settings=GENERATION_SETTINGS,
        generation_trace_store=trace_store,
        generation_trace_mode="all",
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    trace_store.append.assert_awaited_once()
    trace_payload = trace_store.append.await_args.kwargs["record"]
    assert trace_payload["provider"] == "lmstudio"
    assert trace_payload["model"] == "model-a"
    assert trace_payload["finish_reason"] == "stop"
    assert trace_payload["usage"] == {"prompt_tokens": 12, "completion_tokens": 6}
    prompt_stats = trace_payload["prompt_stats"]
    assert isinstance(prompt_stats, dict)
    assert prompt_stats["character_tokens"] > 0
    assert prompt_stats["world_tokens"] > 0
    assert prompt_stats["history_tokens"] > 0
    assert prompt_stats["system_tokens"] > 0
    assert prompt_stats["total_prompt_tokens"] == (
        prompt_stats["system_tokens"] + prompt_stats["history_tokens"]
    )


@pytest.mark.asyncio
async def test_chat_service_writes_generation_trace_only_on_errors(
    session_context: tuple[Session, User, Character, World],
) -> None:
    session, user, character, world = session_context
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(side_effect=RuntimeError("provider down"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=[])
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = []
    session_store = AsyncMock()
    session_store.get_by_id = AsyncMock(return_value=session)
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)
    group_store = AsyncMock()
    character_store = AsyncMock()
    character_store.get_by_id = AsyncMock(return_value=character)
    world_store = AsyncMock()
    world_store.get_by_id = AsyncMock(return_value=world)
    trace_store = AsyncMock()

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
        generation_settings=GENERATION_SETTINGS,
        generation_trace_store=trace_store,
        generation_trace_mode="errors",
    )

    with pytest.raises(RuntimeError, match="provider down"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
        )

    trace_store.append.assert_awaited_once()
    trace_payload = trace_store.append.await_args.kwargs["record"]
    assert trace_payload["finish_reason"] == "error"
    assert trace_payload["error"] == {"type": "RuntimeError", "message": "provider down"}
    prompt_stats = trace_payload["prompt_stats"]
    assert isinstance(prompt_stats, dict)
    assert prompt_stats["total_prompt_tokens"] == (
        prompt_stats["system_tokens"] + prompt_stats["history_tokens"]
    )
