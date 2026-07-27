from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID

import pytest

from rp_engine.application.services.chat_service import (
    FINISH_REASON_LENGTH,
    FINISH_REASON_METADATA_KEY,
    THINKING_METADATA_KEY,
    ChatService,
)
from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.group.group import Group
from rp_engine.core.llm.errors import EmptyGenerationError
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import SessionDirectives
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")
USER_ID = UUID("00000000-0000-0000-0000-000000000042")
GROUP_ID = UUID("00000000-0000-0000-0000-000000000314")
DEFINITION_ID = "scenario-1"
ROLE = "character"
GENERATION_SETTINGS = GenerationSettings(temperature=0.8, max_tokens=600, top_p=0.95)

ScenarioContext = tuple[ScenarioSession, ScenarioDefinition, User]


def _character() -> Character:
    return Character(
        id="belzebuth",
        name="Belzebuth",
        description="{{char}} is a dragon companion of {{user}}.",
        personality="Protective and witty.",
        greeting="Welcome back, {{user}}.",
    )


def _world() -> World:
    return World(
        id="default",
        name="Main World",
        description="{{user}} explores a realm with {{char}}.",
        rules=("Stay in character.",),
    )


def _definition(
    character: Character | None = None, world: World | None = None
) -> ScenarioDefinition:
    return ScenarioDefinition(
        id=DEFINITION_ID,
        owner_id=USER_ID,
        name="Belzebuth",
        description="",
        world=world or _world(),
        characters={ROLE: character or _character()},
    )


def _session(*, owner_kind: str = "user", owner_id: UUID = USER_ID) -> ScenarioSession:
    return ScenarioSession(
        id=SESSION_ID,
        scenario_definition_id=DEFINITION_ID,
        owner_kind=owner_kind,  # type: ignore[arg-type]
        owner_id=owner_id,
        active_participants={ROLE: "belzebuth"},
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def scenario_context() -> ScenarioContext:
    return _session(), _definition(), User(id=USER_ID, display_name="Pablo")


def _build_service(
    *,
    scenario_context: ScenarioContext,
) -> tuple[ChatService, AsyncMock, AsyncMock]:
    session, definition, user = scenario_context

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

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=definition)

    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
    )
    return service, orchestrator, conversation_store


@pytest.mark.asyncio
async def test_chat_service_builds_conversation_and_calls_orchestrator(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)

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
                    metadata={"finish_reason": "stop", "turn": "1"},
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chat_service_persists_thinking_metadata(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
    orchestrator.generate_reply = AsyncMock(
        return_value=LLMResponse(content="scene response", thinking="pondering the scene")
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello there",
    )

    conversation_store.save_message.assert_awaited_with(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content="scene response",
            metadata={"finish_reason": "stop", "turn": "1", "thinking": "pondering the scene"},
        ),
    )


@pytest.mark.asyncio
async def test_chat_service_omits_thinking_metadata_when_absent(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene response"))

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello there",
    )

    conversation_store.save_message.assert_awaited_with(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content="scene response",
            metadata={"finish_reason": "stop", "turn": "1"},
        ),
    )


@pytest.mark.asyncio
async def test_chat_service_rejects_empty_message(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)

    with pytest.raises(ValueError, match="Message must not be empty"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="   ",
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_rejects_invalid_session_identity(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)

    with pytest.raises(ValueError, match="invalid session id"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session("not-a-uuid"),
            message="hello",
        )

    orchestrator.generate_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_continue_saves_character_message(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
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
            metadata={"finish_reason": "stop", "turn": "1"},
        ),
    )


@pytest.mark.asyncio
async def test_continue_advances_when_last_reply_finished_normally(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
    conversation_store.load_messages = AsyncMock(
        return_value=[
            ConversationMessage(role=ConversationRole.USER, content="I look around", metadata={}),
            ConversationMessage(
                role=ConversationRole.CHARACTER,
                content="A door creaks open.",
                metadata={"finish_reason": "stop"},
            ),
        ]
    )
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="advanced"))

    response = await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    assert response == "advanced"
    directive = orchestrator.generate_reply.await_args.args[0].conversation.messages[-1]
    assert directive.metadata == {"source": "continue_command"}
    assert "Continue the narration" in directive.content


@pytest.mark.asyncio
async def test_continue_resumes_when_last_reply_was_truncated(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
    history = [
        ConversationMessage(role=ConversationRole.USER, content="I look around", metadata={}),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content="A door creaks open and behind it",
            metadata={"finish_reason": "length"},
        ),
    ]
    conversation_store.load_messages = AsyncMock(return_value=history)
    service._memory_strategy.build_context.side_effect = lambda messages: list(messages)
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content=" stands a figure."))

    response = await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    assert response == " stands a figure."
    # Resume is an assistant prefill: the truncated reply is the final message and there is
    # no instruction turn to open a new assistant turn.
    conversation = orchestrator.generate_reply.await_args.args[0].conversation
    assert conversation.continue_final_message is True
    assert conversation.metadata["source"] == "resume_command"
    assert conversation.messages[-1].role == ConversationRole.CHARACTER
    assert conversation.messages[-1].content == "A door creaks open and behind it"
    # The resumed continuation is appended as its own narrator turn.
    conversation_store.save_message.assert_awaited_with(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content=" stands a figure.",
            metadata={"finish_reason": "stop", "turn": "2"},
        ),
    )


@pytest.mark.asyncio
async def test_chat_service_regenerate_replaces_last_character_message(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
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
    request = orchestrator.generate_reply.await_args.args[0]
    assert request.conversation.messages[-1].role == ConversationRole.USER
    assert request.conversation.messages[-1].content == "hello"
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
                    metadata={"finish_reason": "stop", "turn": "1"},
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chat_service_regenerate_after_continue_uses_assistant_context(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
    conversation_store.load_messages = AsyncMock(
        return_value=[
            ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
            ConversationMessage(role=ConversationRole.CHARACTER, content="first", metadata={}),
            ConversationMessage(role=ConversationRole.CHARACTER, content="to replace", metadata={}),
        ]
    )
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="new continuation"))

    response = await service.regenerate_last_response(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    assert response == "new continuation"
    request = orchestrator.generate_reply.await_args.args[0]
    assert request.conversation.messages[-1].role == ConversationRole.USER
    assert request.conversation.messages[-1].metadata == {"source": "continue_command"}
    assert "Continue the narration naturally" in request.conversation.messages[-1].content
    conversation_store.clear.assert_awaited_once_with(MemoryKey(f"session_{SESSION_ID}"))
    conversation_store.save_message.assert_has_awaits(
        [
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
            ),
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(role=ConversationRole.CHARACTER, content="first", metadata={}),
            ),
            call(
                MemoryKey(f"session_{SESSION_ID}"),
                ConversationMessage(
                    role=ConversationRole.CHARACTER,
                    content="new continuation",
                    metadata={"finish_reason": "stop", "turn": "2"},
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chat_service_regenerate_requires_latest_character_message(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
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
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, conversation_store = _build_service(scenario_context=scenario_context)
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
    service = ChatService(
        orchestrator=AsyncMock(),
        conversation_store=AsyncMock(),
        memory_strategy=Mock(),
        user_identity_store=AsyncMock(),
        group_identity_store=AsyncMock(),
        scenario_session_store=AsyncMock(),
        scenario_definition_store=AsyncMock(),
        generation_settings=GENERATION_SETTINGS,
    )
    conversation_store = service._conversation_store  # type: ignore[attr-defined]

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

    group_session = _session(owner_kind="group", owner_id=GROUP_ID)
    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=group_session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=_definition())

    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=Group(id=GROUP_ID, display_name="Raid Party"))

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=AsyncMock(),
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
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
    scenario_context: ScenarioContext,
) -> None:
    service, _, conversation_store = _build_service(scenario_context=scenario_context)

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
    scenario_context: ScenarioContext,
) -> None:
    service, _, _ = _build_service(scenario_context=scenario_context)
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
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)
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


def _build_trace_service(
    *,
    scenario_context: ScenarioContext,
    orchestrator: AsyncMock,
    conversation_store: AsyncMock,
    memory_strategy: Mock,
    trace_store: AsyncMock,
    generation_trace_mode: str,
) -> ChatService:
    session, definition, user = scenario_context
    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=definition)
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)
    return ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=AsyncMock(),
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
        generation_trace_store=trace_store,
        generation_trace_mode=generation_trace_mode,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_chat_service_writes_generation_trace_in_all_mode(
    scenario_context: ScenarioContext,
) -> None:
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
            thinking="weighing the options",
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
    trace_store = AsyncMock()

    service = _build_trace_service(
        scenario_context=scenario_context,
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        trace_store=trace_store,
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
    assert trace_payload["thinking"] == "weighing the options"
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
    scenario_context: ScenarioContext,
) -> None:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(side_effect=RuntimeError("provider down"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=[])
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = []
    trace_store = AsyncMock()

    service = _build_trace_service(
        scenario_context=scenario_context,
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        trace_store=trace_store,
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


def _build_service_with_session_store(
    session: ScenarioSession,
    *,
    fail_generation: bool = False,
) -> tuple[ChatService, AsyncMock, AsyncMock]:
    """A service whose session store is observable, for the director-instruction lifecycle."""
    orchestrator = AsyncMock()
    if fail_generation:
        orchestrator.generate_reply = AsyncMock(side_effect=RuntimeError("provider down"))
    else:
        orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene"))

    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[ConversationMessage(role=ConversationRole.USER, content="previous")]
    )
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = []

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=_definition())
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=User(id=USER_ID, display_name="Pablo"))
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
    )
    return service, scenario_session_store, orchestrator


@pytest.mark.asyncio
async def test_director_instruction_is_cleared_after_a_successful_turn() -> None:
    session = _session().with_directives(
        SessionDirectives().with_director_instruction("Raise the stakes.")
    )
    service, session_store, _ = _build_service_with_session_store(session)

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    session_store.save.assert_awaited_once()
    saved = session_store.save.await_args.args[0]
    assert saved.directives.director_instruction == ""


@pytest.mark.asyncio
async def test_director_instruction_reaches_the_prompt_of_the_turn_that_consumes_it() -> None:
    session = _session().with_directives(
        SessionDirectives().with_director_instruction("Raise the stakes.")
    )
    service, _, orchestrator = _build_service_with_session_store(session)

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    request = orchestrator.generate_reply.await_args.args[0]
    assert any("Raise the stakes." in message.content for message in request.conversation.messages)


@pytest.mark.asyncio
async def test_director_instruction_survives_a_failed_generation() -> None:
    """A failed turn keeps the instruction alive for the retry the player is about to make."""
    session = _session().with_directives(
        SessionDirectives().with_director_instruction("Raise the stakes.")
    )
    service, session_store, _ = _build_service_with_session_store(session, fail_generation=True)

    with pytest.raises(RuntimeError, match="provider down"):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
        )

    session_store.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_without_director_instruction_is_not_rewritten() -> None:
    service, session_store, _ = _build_service_with_session_store(_session())

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    session_store.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_continue_clears_the_director_instruction() -> None:
    session = _session().with_directives(
        SessionDirectives().with_director_instruction("Raise the stakes.")
    )
    service, session_store, _ = _build_service_with_session_store(session)

    await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    session_store.save.assert_awaited_once()
    assert session_store.save.await_args.args[0].directives.director_instruction == ""


@pytest.mark.asyncio
async def test_persistent_directives_are_left_untouched_by_a_turn() -> None:
    directives, _ = SessionDirectives().with_language("fr").with_rule("No time skips.")
    session = _session().with_directives(directives.with_director_instruction("Now."))
    service, session_store, _ = _build_service_with_session_store(session)

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    saved = session_store.save.await_args.args[0]
    assert saved.directives.language == "fr"
    assert [rule.text for rule in saved.directives.rules] == ["No time skips."]


def _empty_reply_service(
    *,
    thinking: str | None = "burned the whole budget reasoning",
    finish_reason: str = "length",
) -> tuple[ChatService, AsyncMock, AsyncMock]:
    """A service whose model returns reasoning but no prose — the reasoning-model failure
    mode where `max_tokens` is consumed before any reply is written."""
    session = _session()
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(
        return_value=LLMResponse(
            content="   \n  ",
            finish_reason=finish_reason,  # type: ignore[arg-type]
            thinking=thinking,
        )
    )
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[
            ConversationMessage(role=ConversationRole.USER, content="previous"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="cut off mid-"),
        ]
    )
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = []

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(
        return_value=session.with_directives(
            SessionDirectives().with_director_instruction("Raise the stakes.")
        )
    )
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=_definition())
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=User(id=USER_ID, display_name="Pablo"))
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)
    trace_store = AsyncMock()

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
        generation_trace_store=trace_store,
        generation_trace_mode="all",
    )
    return service, conversation_store, trace_store


@pytest.mark.asyncio
async def test_empty_reply_is_rejected_and_nothing_is_persisted() -> None:
    service, conversation_store, _ = _empty_reply_service()

    with pytest.raises(EmptyGenerationError) as excinfo:
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
        )

    assert excinfo.value.finish_reason == "length"
    # Neither the player's message nor an empty narrator turn reaches the conversation.
    conversation_store.save_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_reply_is_still_traced_for_debugging() -> None:
    service, _, trace_store = _empty_reply_service()

    with pytest.raises(EmptyGenerationError):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
        )

    trace_store.append.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_reply_does_not_burn_the_director_instruction() -> None:
    """The note was aimed at a reply the player never saw, so it must survive for the retry."""
    service, _, _ = _empty_reply_service()
    session_store = service._scenario_session_store  # type: ignore[attr-defined]

    with pytest.raises(EmptyGenerationError):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
        )

    session_store.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_continue_does_not_append_a_resumable_empty_turn() -> None:
    """The loop this prevents: an empty turn stored with `finish_reason: length` makes the
    next `/continue` try to resume nothing, producing another empty turn."""
    service, conversation_store, _ = _empty_reply_service()

    with pytest.raises(EmptyGenerationError):
        await service.continue_story(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        )

    conversation_store.save_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_regenerate_does_not_destroy_the_existing_history() -> None:
    service, conversation_store, _ = _empty_reply_service()

    with pytest.raises(EmptyGenerationError):
        await service.regenerate_last_response(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        )

    conversation_store.clear.assert_not_awaited()
    conversation_store.save_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_whitespace_only_reply_counts_as_empty() -> None:
    service, _, _ = _empty_reply_service(thinking=None, finish_reason="stop")

    with pytest.raises(EmptyGenerationError) as excinfo:
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="hello",
        )

    assert excinfo.value.finish_reason == "stop"


@pytest.mark.asyncio
async def test_continue_builds_an_assistant_prefill_from_the_truncated_turn() -> None:
    """End of the chain: LM Studio reports `length` → the turn is stored → `/continue` builds
    an assistant prefill, so the model continues those exact tokens without re-planning."""
    session = _session()
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="…and she left."))
    truncated = ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="She reached for the door and",
        metadata={
            FINISH_REASON_METADATA_KEY: FINISH_REASON_LENGTH,
            THINKING_METADATA_KEY: "Plan: she hesitates, then leaves without a word.",
        },
    )
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=[truncated])
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = [truncated]

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=_definition())
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=User(id=USER_ID, display_name="Pablo"))
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
    )

    await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    conversation = orchestrator.generate_reply.await_args.args[0].conversation
    assert conversation.continue_final_message is True
    assert conversation.messages[-1].role == ConversationRole.CHARACTER
    assert conversation.messages[-1].content == "She reached for the door and"


@pytest.mark.asyncio
async def test_plain_continue_does_not_receive_prior_reasoning() -> None:
    """A turn that ended naturally is advanced, not resumed — no notes, no resume directive."""
    session = _session()
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="next beat"))
    finished = ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="She left.",
        metadata={
            FINISH_REASON_METADATA_KEY: "stop",
            THINKING_METADATA_KEY: "Plan: she hesitates, then leaves.",
        },
    )
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=[finished])
    memory_strategy = Mock()
    memory_strategy.build_context.return_value = [finished]

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=_definition())
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=User(id=USER_ID, display_name="Pablo"))
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
    )

    await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    conversation = orchestrator.generate_reply.await_args.args[0].conversation
    assert conversation.continue_final_message is False
    assert "Continue the narration naturally" in conversation.messages[-1].content


def _retry_service(history: list[ConversationMessage]) -> tuple[ChatService, AsyncMock]:
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="regenerated"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=history)
    memory_strategy = Mock()
    memory_strategy.build_context.side_effect = lambda messages: list(messages)

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=_session())
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=_definition())
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=User(id=USER_ID, display_name="Pablo"))
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
    )
    return service, orchestrator


@pytest.mark.asyncio
async def test_retrying_a_resumed_turn_prefills_the_truncated_turn_again() -> None:
    """`/retry` drops the failed turn, so the *truncated* turn becomes last again and the
    replacement attempt is a prefill of that text — not of the discarded turn's."""
    truncated = ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="She reached for the door and",
        metadata={
            FINISH_REASON_METADATA_KEY: FINISH_REASON_LENGTH,
            THINKING_METADATA_KEY: "TRUNCATED-TURN-PLAN",
        },
    )
    failed_resume = ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="…hesitated.",
        metadata={
            FINISH_REASON_METADATA_KEY: "stop",
            THINKING_METADATA_KEY: "DISCARDED-TURN-PLAN",
        },
    )
    service, orchestrator = _retry_service(
        [
            ConversationMessage(role=ConversationRole.USER, content="go on"),
            truncated,
            failed_resume,
        ]
    )

    await service.regenerate_last_response(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    conversation = orchestrator.generate_reply.await_args.args[0].conversation
    assert conversation.continue_final_message is True
    assert conversation.messages[-1].content == "She reached for the door and"
    assert not any("…hesitated." in message.content for message in conversation.messages)


@pytest.mark.asyncio
async def test_retrying_after_a_naturally_ended_turn_still_advances() -> None:
    service, orchestrator = _retry_service(
        [
            ConversationMessage(role=ConversationRole.USER, content="go on"),
            ConversationMessage(
                role=ConversationRole.CHARACTER,
                content="She left.",
                metadata={FINISH_REASON_METADATA_KEY: "stop"},
            ),
            ConversationMessage(role=ConversationRole.CHARACTER, content="A new beat."),
        ]
    )

    await service.regenerate_last_response(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    conversation = orchestrator.generate_reply.await_args.args[0].conversation
    assert conversation.continue_final_message is False
    assert "Continue the narration naturally" in conversation.messages[-1].content
