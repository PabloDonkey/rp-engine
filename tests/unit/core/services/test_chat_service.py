import asyncio
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, call
from uuid import UUID

import pytest

from rp_engine.application.services.chat_service import (
    FINISH_REASON_LENGTH,
    FINISH_REASON_METADATA_KEY,
    THINKING_METADATA_KEY,
    ChatService,
    SessionBusyError,
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
from rp_engine.core.memory.character_ratio_token_counter import CharacterRatioTokenCounter
from rp_engine.core.memory.context_budget import ContextBudget
from rp_engine.core.memory.fragment import MemorySystemId
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.memory.pipeline import MemoryPipeline
from rp_engine.core.memory.recall_context import MemoryObserveContext
from rp_engine.core.memory.recent_window_source import RecentWindowSource
from rp_engine.core.ports import BackgroundJob
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

# Token counting is faked, not mocked: the character-ratio counter is the real fallback
# implementation, so these tests exercise the same arithmetic the engine runs.
TOKEN_COUNTER = CharacterRatioTokenCounter()


class _FixedContextWindow:
    """A model with a known window, so a test can say how much room memory has."""

    def __init__(self, tokens: int) -> None:
        self._tokens = tokens

    async def context_length(self) -> int:
        return self._tokens


def _memory_pipeline(*, context_length: int = 1_000_000) -> MemoryPipeline:
    """The real pipeline over the real window source. The default window is far larger
    than any prompt these tests build, so the whole stored history is replayed — which is
    what every test here assumed before the budget existed."""
    return MemoryPipeline(
        sources=[RecentWindowSource(token_counter=TOKEN_COUNTER)],
        context_budget=ContextBudget(context_window=_FixedContextWindow(context_length), share=1.0),
    )


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


class RecordingTaskScheduler:
    """Runs nothing. It records what the turn asked the background worker to do."""

    def __init__(self) -> None:
        self.submitted: list[str] = []
        self.jobs: list[BackgroundJob] = []

    def submit(self, *, key: str, job: BackgroundJob) -> bool:
        self.submitted.append(key)
        self.jobs.append(job)
        return True


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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
        user_identity_store=AsyncMock(),
        group_identity_store=AsyncMock(),
        scenario_session_store=AsyncMock(),
        scenario_definition_store=AsyncMock(),
        generation_settings=GENERATION_SETTINGS,
    )
    conversation_store = cast(AsyncMock, service._conversation_store)

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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
    trace_store = AsyncMock()

    service = _build_trace_service(
        scenario_context=scenario_context,
        orchestrator=orchestrator,
        conversation_store=conversation_store,
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
    trace_store = AsyncMock()

    service = _build_trace_service(
        scenario_context=scenario_context,
        orchestrator=orchestrator,
        conversation_store=conversation_store,
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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
    assert saved.directives.director_instructions == ()


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
    assert session_store.save.await_args.args[0].directives.director_instructions == ()


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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
    session_store = cast(AsyncMock, service._scenario_session_store)

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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
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


LENGTH_RETRY_SETTINGS = GenerationSettings(temperature=0.8, max_tokens=4000, top_p=0.95)


def _length_retry_service(
    *,
    responses: list[LLMResponse],
    history: list[ConversationMessage] | None = None,
) -> tuple[ChatService, AsyncMock, AsyncMock]:
    """A service that recovers once from the token cap, with a scripted model."""
    stored = history if history is not None else []
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(side_effect=responses)
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=stored)

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
        memory_pipeline=_memory_pipeline(),
        token_counter=TOKEN_COUNTER,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
        length_retry_settings=LENGTH_RETRY_SETTINGS,
    )
    return service, orchestrator, conversation_store


@pytest.mark.asyncio
async def test_truncated_reply_is_resumed_automatically_and_delivered_as_one_turn() -> None:
    """The player asked for one reply and gets one reply, even though the cap split it."""
    service, orchestrator, conversation_store = _length_retry_service(
        responses=[
            LLMResponse(content="She reached for the door and", finish_reason="length"),
            LLMResponse(content=" stepped into the rain.", finish_reason="stop"),
        ]
    )

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I follow her",
    )

    assert response == "She reached for the door and stepped into the rain."
    # The second attempt is a prefill that carries the half-written reply.
    retry = orchestrator.generate_reply.await_args_list[1].args[0]
    assert retry.conversation.continue_final_message is True
    assert retry.conversation.messages[-1].role == ConversationRole.CHARACTER
    assert retry.conversation.messages[-1].content == "She reached for the door and"
    # The player's own message is still in front of it, or the model would resume blind.
    assert retry.conversation.messages[-2].content == "I follow her"
    # One narrator turn is stored, holding both halves and the finish reason of the retry.
    conversation_store.save_message.assert_awaited_with(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content="She reached for the door and stepped into the rain.",
            metadata={FINISH_REASON_METADATA_KEY: "stop", "turn": "1"},
        ),
    )


@pytest.mark.asyncio
async def test_reasoning_only_reply_is_retried_with_the_larger_budget() -> None:
    """The turn-85 failure: the whole cap went on thinking, so there is nothing to resume
    and the same request is re-run with more room."""
    service, orchestrator, _ = _length_retry_service(
        responses=[
            LLMResponse(content="  \n ", finish_reason="length", thinking="planning at length"),
            LLMResponse(content="She looks up.", finish_reason="stop"),
        ]
    )

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I wait",
    )

    assert response == "She looks up."
    first, retry = (call.args[0] for call in orchestrator.generate_reply.await_args_list)
    # Same prompt, bigger budget — nothing else would make the second attempt differ.
    assert retry.conversation == first.conversation
    assert retry.settings == LENGTH_RETRY_SETTINGS
    assert first.settings == GENERATION_SETTINGS


@pytest.mark.asyncio
async def test_recovery_gives_up_after_one_retry() -> None:
    """A second cap hit is stored as truncated, so `/continue` can carry on by hand."""
    service, orchestrator, conversation_store = _length_retry_service(
        responses=[
            LLMResponse(content="She reached for", finish_reason="length"),
            LLMResponse(content=" the door and", finish_reason="length"),
        ]
    )

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I follow her",
    )

    assert response == "She reached for the door and"
    assert orchestrator.generate_reply.await_count == 2
    conversation_store.save_message.assert_awaited_with(
        MemoryKey(f"session_{SESSION_ID}"),
        ConversationMessage(
            role=ConversationRole.CHARACTER,
            content="She reached for the door and",
            metadata={FINISH_REASON_METADATA_KEY: FINISH_REASON_LENGTH, "turn": "1"},
        ),
    )


@pytest.mark.asyncio
async def test_a_full_context_window_is_not_retried() -> None:
    """`context_length` means the window is full; a second attempt hits the same wall."""
    service, orchestrator, _ = _length_retry_service(
        responses=[LLMResponse(content="She reached for", finish_reason="context_length")]
    )

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I follow her",
    )

    assert response == "She reached for"
    assert orchestrator.generate_reply.await_count == 1


@pytest.mark.asyncio
async def test_recovery_is_off_when_no_retry_settings_are_wired() -> None:
    service, orchestrator, _ = _build_service(
        scenario_context=(_session(), _definition(), User(id=USER_ID, display_name="Pablo"))
    )
    orchestrator.generate_reply = AsyncMock(
        return_value=LLMResponse(content="cut off mid-", finish_reason="length")
    )

    response = await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I follow her",
    )

    assert response == "cut off mid-"
    assert orchestrator.generate_reply.await_count == 1


@pytest.mark.asyncio
async def test_continue_that_is_cut_off_resumes_from_the_stored_text_too() -> None:
    """A resumed turn that is itself cut off must continue the whole sentence, not just the
    part this call produced."""
    truncated = ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="She reached for",
        metadata={FINISH_REASON_METADATA_KEY: FINISH_REASON_LENGTH},
    )
    service, orchestrator, _ = _length_retry_service(
        responses=[
            LLMResponse(content=" the door and", finish_reason="length"),
            LLMResponse(content=" stepped out.", finish_reason="stop"),
        ],
        history=[
            ConversationMessage(role=ConversationRole.USER, content="I follow her"),
            truncated,
        ],
    )

    response = await service.continue_story(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
    )

    # Only the new text is returned; the stored half is already on screen.
    assert response == " the door and stepped out."
    retry = orchestrator.generate_reply.await_args_list[1].args[0]
    assert retry.conversation.messages[-1].content == "She reached for the door and"


@pytest.mark.asyncio
async def test_each_recovery_attempt_is_traced_separately() -> None:
    service, _, _ = _length_retry_service(
        responses=[
            LLMResponse(content="She reached for", finish_reason="length"),
            LLMResponse(content=" the door.", finish_reason="stop"),
        ]
    )
    trace_store = AsyncMock()
    service._generation_trace_store = trace_store
    service._generation_trace_mode = "all"

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="I follow her",
    )

    assert trace_store.append.await_count == 2


@pytest.mark.asyncio
async def test_trace_prompt_sections_are_read_by_label_not_by_position() -> None:
    """The debug prompt used to slice system messages by position — slot 0 as the
    character, 1 as the world, 2 as the conversation rules. Every section added since then
    shifted those indices. A scenario with an overview adds one section ahead of the
    character, which is enough to make the positional read return the wrong three."""
    definition = ScenarioDefinition(
        id=DEFINITION_ID,
        owner_id=USER_ID,
        name="Belzebuth",
        description="A long ride through the ash flats.",
        world=_world(),
        characters={ROLE: _character()},
    )
    session = _session().with_directives(SessionDirectives().with_language("fr"))
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=[])
    trace_store = AsyncMock()

    service = _build_trace_service(
        scenario_context=(session, definition, User(id=USER_ID, display_name="Pablo")),
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        trace_store=trace_store,
        generation_trace_mode="all",
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    prompt = trace_store.append.await_args.kwargs["record"]["prompt"]
    assert prompt["character"].startswith("[Character]")
    assert prompt["world"].startswith("[World]")
    assert prompt["conversation_rules"].startswith("[Response Format]")


@pytest.mark.asyncio
async def test_what_the_context_budget_dropped_lands_in_the_trace(
    scenario_context: ScenarioContext,
) -> None:
    """The player is never told that old turns left the prompt. The number lives here."""
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(
        return_value=[
            ConversationMessage(role=ConversationRole.USER, content=f"turn {index}")
            for index in range(200)
        ]
    )
    trace_store = AsyncMock()
    session, definition, user = scenario_context
    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=definition)
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)
    # A window with room for a few dozen turns beside the static prompt sections, and a
    # story far longer than that.
    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_pipeline=_memory_pipeline(context_length=600),
        token_counter=TOKEN_COUNTER,
        user_identity_store=user_store,
        group_identity_store=AsyncMock(),
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
        generation_trace_store=trace_store,
        generation_trace_mode="all",
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello",
    )

    memory = trace_store.append.await_args.kwargs["record"]["memory"]
    assert memory["dropped_messages"] > 0
    assert memory["used_tokens"] <= memory["budget_tokens"]
    conversation = orchestrator.generate_reply.await_args.args[0].conversation
    replayed = [
        message.content
        for message in conversation.messages
        if message.role != ConversationRole.SYSTEM
    ]
    # Whatever survived is the newest end of the story, and no message is half there.
    assert replayed[-1] == "hello"
    assert all(content.startswith("turn ") for content in replayed[:-1])


def _service_with_scheduler(
    *,
    scenario_context: ScenarioContext,
    history: list[ConversationMessage],
    memory_pipeline: MemoryPipeline | None = None,
) -> tuple[ChatService, RecordingTaskScheduler, AsyncMock]:
    session, definition, user = scenario_context
    orchestrator = AsyncMock()
    orchestrator.generate_reply = AsyncMock(return_value=LLMResponse(content="scene response"))
    conversation_store = AsyncMock()
    conversation_store.load_messages = AsyncMock(return_value=history)

    scenario_session_store = AsyncMock()
    scenario_session_store.get_by_id = AsyncMock(return_value=session)
    scenario_definition_store = AsyncMock()
    scenario_definition_store.get_by_id = AsyncMock(return_value=definition)
    user_store = AsyncMock()
    user_store.get_by_id = AsyncMock(return_value=user)
    group_store = AsyncMock()
    group_store.get_by_id = AsyncMock(return_value=None)

    scheduler = RecordingTaskScheduler()
    service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_pipeline=memory_pipeline or _memory_pipeline(),
        token_counter=TOKEN_COUNTER,
        user_identity_store=user_store,
        group_identity_store=group_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=GENERATION_SETTINGS,
        task_scheduler=scheduler,
    )
    return service, scheduler, conversation_store


@pytest.mark.asyncio
async def test_a_finished_turn_asks_the_memory_layers_to_catch_up(
    scenario_context: ScenarioContext,
) -> None:
    service, scheduler, _ = _service_with_scheduler(
        scenario_context=scenario_context,
        history=[ConversationMessage(role=ConversationRole.USER, content="previous")],
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
        message="hello there",
    )

    # One key per session: two fast turns must collapse into one pass, not race.
    assert scheduler.submitted == [f"memory:{SESSION_ID}"]


@pytest.mark.asyncio
async def test_continue_and_retry_ask_the_memory_layers_too(
    scenario_context: ScenarioContext,
) -> None:
    history = [
        ConversationMessage(role=ConversationRole.USER, content="previous"),
        ConversationMessage(role=ConversationRole.CHARACTER, content="a reply"),
    ]
    service, scheduler, _ = _service_with_scheduler(
        scenario_context=scenario_context, history=history
    )
    identity = ConversationIdentity.for_session(str(SESSION_ID))

    await service.continue_story(conversation_identity=identity)
    await service.regenerate_last_response(conversation_identity=identity)

    assert scheduler.submitted == [f"memory:{SESSION_ID}", f"memory:{SESSION_ID}"]


@pytest.mark.asyncio
async def test_a_failed_turn_asks_nothing(scenario_context: ScenarioContext) -> None:
    """Nothing was stored, so there is nothing for the memory layers to catch up with."""
    service, scheduler, _ = _service_with_scheduler(
        scenario_context=scenario_context,
        history=[ConversationMessage(role=ConversationRole.USER, content="previous")],
    )

    with pytest.raises(ValueError):
        await service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="   ",
        )

    assert scheduler.submitted == []


@pytest.mark.asyncio
async def test_the_submitted_job_runs_the_pipeline_write_half(
    scenario_context: ScenarioContext,
) -> None:
    """The job is a question about stored state, so it can run at any time — including
    now, in the test, with no event loop of its own."""
    session, _, _ = scenario_context
    observed: list[int] = []

    class RecordingSource:
        id: MemorySystemId = "rolling_summary"

        async def recall(self, context: object) -> tuple[()]:
            return ()

        async def observe(self, context: MemoryObserveContext) -> None:
            observed.append(context.turn)

    service, scheduler, _ = _service_with_scheduler(
        scenario_context=scenario_context,
        history=[ConversationMessage(role=ConversationRole.USER, content="previous")],
        memory_pipeline=MemoryPipeline(
            sources=[RecordingSource()],
            context_budget=ContextBudget(context_window=_FixedContextWindow(1000), share=1.0),
        ),
    )

    await service.send_message(
        conversation_identity=ConversationIdentity.for_session(str(session.id)),
        message="hello there",
    )
    await scheduler.jobs[0]()

    assert observed == [1]


OTHER_SESSION_ID = UUID("00000000-0000-0000-0000-000000000222")


def _blocking_generation(
    orchestrator: AsyncMock,
) -> tuple[asyncio.Event, asyncio.Event]:
    """Hold a generation open so a second turn can be attempted while it runs."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow(_: GenerationRequest) -> LLMResponse:
        started.set()
        await release.wait()
        return LLMResponse(content="held reply", finish_reason="stop", metadata={})

    orchestrator.generate_reply = AsyncMock(side_effect=_slow)
    return started, release


@pytest.mark.asyncio
async def test_a_second_turn_is_refused_while_the_first_is_generating(
    scenario_context: ScenarioContext,
) -> None:
    """Telegram and the panel both reach one story. Only one of them may generate."""
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)
    started, release = _blocking_generation(orchestrator)
    identity = ConversationIdentity.for_session(str(SESSION_ID))

    first = asyncio.create_task(
        service.send_message(conversation_identity=identity, message="from telegram")
    )
    await started.wait()

    with pytest.raises(SessionBusyError):
        await service.send_message(conversation_identity=identity, message="from the panel")

    release.set()
    assert await first == "held reply"
    # The refused turn never reached the model.
    assert orchestrator.generate_reply.await_count == 1


@pytest.mark.asyncio
async def test_continue_and_retry_are_refused_by_the_same_guard(
    scenario_context: ScenarioContext,
) -> None:
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)
    started, release = _blocking_generation(orchestrator)
    identity = ConversationIdentity.for_session(str(SESSION_ID))

    first = asyncio.create_task(
        service.send_message(conversation_identity=identity, message="from telegram")
    )
    await started.wait()

    with pytest.raises(SessionBusyError):
        await service.continue_story(conversation_identity=identity)
    with pytest.raises(SessionBusyError):
        await service.regenerate_last_response(conversation_identity=identity)

    release.set()
    await first


@pytest.mark.asyncio
async def test_a_different_session_is_not_blocked(scenario_context: ScenarioContext) -> None:
    """The guard is per story, not global. One busy session must not stall every other."""
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)
    started, release = _blocking_generation(orchestrator)

    first = asyncio.create_task(
        service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(SESSION_ID)),
            message="from telegram",
        )
    )
    await started.wait()

    second = asyncio.create_task(
        service.send_message(
            conversation_identity=ConversationIdentity.for_session(str(OTHER_SESSION_ID)),
            message="a different story",
        )
    )
    await asyncio.sleep(0)
    release.set()

    assert await first == "held reply"
    assert await second == "held reply"


@pytest.mark.asyncio
async def test_the_guard_releases_when_a_generation_fails(
    scenario_context: ScenarioContext,
) -> None:
    """A turn that raises must not lock the story out until the process restarts."""
    service, orchestrator, _ = _build_service(scenario_context=scenario_context)
    orchestrator.generate_reply = AsyncMock(side_effect=RuntimeError("provider down"))
    identity = ConversationIdentity.for_session(str(SESSION_ID))

    with pytest.raises(RuntimeError, match="provider down"):
        await service.send_message(conversation_identity=identity, message="one")

    orchestrator.generate_reply = AsyncMock(
        return_value=LLMResponse(content="second try", finish_reason="stop", metadata={})
    )
    assert await service.send_message(conversation_identity=identity, message="two") == "second try"
