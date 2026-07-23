import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.builder import ConversationBuilder, ScenarioConversationInput
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.group.group import Group
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.ports import (
    ConversationStore,
    FeedbackContext,
    GenerationTraceStore,
    GroupIdentityStore,
    MemoryStrategy,
    NoOpProcessingFeedback,
    ProcessingFeedback,
    ScenarioDefinitionStore,
    ScenarioSessionStore,
    UserIdentityStore,
    processing_feedback_scope,
)
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

logger = logging.getLogger(__name__)

# Conversation-message metadata key recording the LLM's stop reason for a narrator turn.
FINISH_REASON_METADATA_KEY = "finish_reason"
# finish_reason value that means the model hit its token limit mid-reply.
FINISH_REASON_LENGTH = "length"


@dataclass(frozen=True, slots=True)
class _ScenarioContext:
    definition: ScenarioDefinition
    session: ScenarioSession
    user: User
    character: Character | None
    world: World | None


class ChatService:
    def __init__(
        self,
        orchestrator: RPOrchestrator,
        conversation_store: ConversationStore,
        memory_strategy: MemoryStrategy,
        user_identity_store: UserIdentityStore,
        group_identity_store: GroupIdentityStore,
        scenario_session_store: ScenarioSessionStore,
        scenario_definition_store: ScenarioDefinitionStore,
        generation_settings: GenerationSettings,
        generation_trace_store: GenerationTraceStore | None = None,
        generation_trace_mode: Literal["off", "errors", "all"] = "off",
    ) -> None:
        self._orchestrator = orchestrator
        self._conversation_store = conversation_store
        self._memory_strategy = memory_strategy
        self._user_identity_store = user_identity_store
        self._group_identity_store = group_identity_store
        self._scenario_session_store = scenario_session_store
        self._scenario_definition_store = scenario_definition_store
        self._generation_settings = generation_settings
        self._generation_trace_store = generation_trace_store
        self._generation_trace_mode = generation_trace_mode
        self._conversation_builder = ConversationBuilder()

    async def send_message(
        self,
        *,
        conversation_identity: ConversationIdentity,
        message: str,
        user_id: str | None = None,
        username: str | None = None,
        display_name: str | None = None,
        processing_feedback: ProcessingFeedback | None = None,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        memory_key = conversation_identity.to_memory_key()
        logger.info(
            "ChatService called",
            extra={"memory_key": memory_key.value, "session_id": str(session_id)},
        )
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("Message must not be empty.")

        context = await self._load_scenario_context(session_id=session_id)
        session = context.session
        feedback = processing_feedback or NoOpProcessingFeedback()
        async with processing_feedback_scope(feedback, context=self._feedback_context(context)):
            history = await self._conversation_store.load_messages(memory_key)
            context_messages = self._memory_strategy.build_context(history)
            conversation = self._conversation_builder.build(
                self._build_input(
                    context,
                    memory_messages=context_messages,
                    user_message=cleaned_message,
                )
            )
            request = GenerationRequest(
                memory_key=memory_key,
                conversation=conversation,
                settings=self._generation_settings,
            )
            request_id = str(uuid4())
            turn = self._resolve_turn(history)
            started_at = perf_counter()

            try:
                llm_response = await self._orchestrator.generate_reply(request)
            except Exception as exc:
                await self._append_generation_trace(
                    session_id=session.id,
                    turn=turn,
                    request_id=request_id,
                    conversation=conversation,
                    generation_settings=request.settings,
                    memory_messages=context_messages,
                    response=None,
                    latency_ms=self._to_latency_ms(started_at),
                    error=exc,
                )
                raise

            await self._append_generation_trace(
                session_id=session.id,
                turn=turn,
                request_id=request_id,
                conversation=conversation,
                generation_settings=request.settings,
                memory_messages=context_messages,
                response=llm_response,
                latency_ms=self._to_latency_ms(started_at),
            )
            character_response = llm_response.content
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(
                role=ConversationRole.USER,
                content=cleaned_message,
                metadata={
                    key: value
                    for key, value in {
                        "user_id": user_id,
                        "username": username,
                        "display_name": display_name,
                    }.items()
                    if value is not None
                },
            ),
        )
        await self._conversation_store.save_message(
            memory_key,
            self._narrator_message(llm_response),
        )
        return character_response

    async def continue_story(
        self,
        *,
        conversation_identity: ConversationIdentity,
        processing_feedback: ProcessingFeedback | None = None,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        memory_key = conversation_identity.to_memory_key()
        logger.info(
            "ChatService continue called",
            extra={"memory_key": memory_key.value, "session_id": str(session_id)},
        )
        context = await self._load_scenario_context(session_id=session_id)
        session = context.session
        feedback = processing_feedback or NoOpProcessingFeedback()
        async with processing_feedback_scope(feedback, context=self._feedback_context(context)):
            history = await self._conversation_store.load_messages(memory_key)
            context_messages = self._memory_strategy.build_context(history)
            builder_input = self._build_input(
                context,
                memory_messages=context_messages,
                user_message="continue",
            )
            # If the last narrator reply was cut off at the token limit, resume it
            # in place; otherwise advance the story with no player input.
            if self._should_resume(history):
                conversation = self._conversation_builder.build_resume(builder_input)
            else:
                conversation = self._conversation_builder.build_continue(builder_input)
            request = GenerationRequest(
                memory_key=memory_key,
                conversation=conversation,
                settings=self._generation_settings,
            )
            request_id = str(uuid4())
            turn = self._resolve_turn(history)
            started_at = perf_counter()

            try:
                llm_response = await self._orchestrator.generate_reply(request)
            except Exception as exc:
                await self._append_generation_trace(
                    session_id=session.id,
                    turn=turn,
                    request_id=request_id,
                    conversation=conversation,
                    generation_settings=request.settings,
                    memory_messages=context_messages,
                    response=None,
                    latency_ms=self._to_latency_ms(started_at),
                    error=exc,
                )
                raise

            await self._append_generation_trace(
                session_id=session.id,
                turn=turn,
                request_id=request_id,
                conversation=conversation,
                generation_settings=request.settings,
                memory_messages=context_messages,
                response=llm_response,
                latency_ms=self._to_latency_ms(started_at),
            )
            character_response = llm_response.content
        await self._conversation_store.save_message(
            memory_key,
            self._narrator_message(llm_response),
        )
        return character_response

    async def regenerate_last_response(
        self,
        *,
        conversation_identity: ConversationIdentity,
        processing_feedback: ProcessingFeedback | None = None,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        memory_key = conversation_identity.to_memory_key()
        logger.info(
            "ChatService regenerate called",
            extra={"memory_key": memory_key.value, "session_id": str(session_id)},
        )
        context = await self._load_scenario_context(session_id=session_id)
        session = context.session
        feedback = processing_feedback or NoOpProcessingFeedback()
        async with processing_feedback_scope(feedback, context=self._feedback_context(context)):
            history = await self._conversation_store.load_messages(memory_key)
            if not history:
                raise ValueError("Conversation is empty. Nothing to regenerate.")
            if history[-1].role != ConversationRole.CHARACTER:
                raise ValueError(
                    "Last message is not a character reply. Regenerate is not available yet."
                )

            trimmed_history = history[:-1]
            if not trimmed_history:
                raise ValueError("Conversation has no user message to regenerate from.")

            latest_context_message = trimmed_history[-1]
            if latest_context_message.role == ConversationRole.USER:
                latest_user_index = self._find_latest_user_index(trimmed_history)
                if latest_user_index is None:
                    raise ValueError("Conversation has no user message to regenerate from.")

                last_user = trimmed_history[latest_user_index]
                prior_history = trimmed_history[:latest_user_index]
                context_messages = self._memory_strategy.build_context(prior_history)
                conversation = self._conversation_builder.build(
                    self._build_input(
                        context,
                        memory_messages=context_messages,
                        user_message=last_user.content,
                    )
                )
            elif latest_context_message.role == ConversationRole.CHARACTER:
                context_messages = self._memory_strategy.build_context(trimmed_history)
                conversation = self._conversation_builder.build_continue(
                    self._build_input(
                        context,
                        memory_messages=context_messages,
                        user_message="continue",
                    )
                )
            else:
                raise ValueError("Conversation has no valid context to regenerate from.")
            request = GenerationRequest(
                memory_key=memory_key,
                conversation=conversation,
                settings=self._generation_settings,
            )
            request_id = str(uuid4())
            turn = self._resolve_turn(trimmed_history)
            started_at = perf_counter()

            try:
                llm_response = await self._orchestrator.generate_reply(request)
            except Exception as exc:
                await self._append_generation_trace(
                    session_id=session.id,
                    turn=turn,
                    request_id=request_id,
                    conversation=conversation,
                    generation_settings=request.settings,
                    memory_messages=context_messages,
                    response=None,
                    latency_ms=self._to_latency_ms(started_at),
                    error=exc,
                )
                raise

            await self._append_generation_trace(
                session_id=session.id,
                turn=turn,
                request_id=request_id,
                conversation=conversation,
                generation_settings=request.settings,
                memory_messages=context_messages,
                response=llm_response,
                latency_ms=self._to_latency_ms(started_at),
            )
            character_response = llm_response.content

        await self._conversation_store.clear(memory_key)
        for message in trimmed_history:
            await self._conversation_store.save_message(memory_key, message)
        await self._conversation_store.save_message(
            memory_key,
            self._narrator_message(llm_response),
        )
        return character_response

    async def clear_conversation(
        self,
        *,
        conversation_identity: ConversationIdentity,
    ) -> None:
        memory_key = conversation_identity.to_memory_key()
        logger.info("ChatService clear called", extra={"memory_key": memory_key.value})
        await self._conversation_store.clear(memory_key)

    @staticmethod
    def _require_session_identity(conversation_identity: ConversationIdentity) -> UUID:
        if conversation_identity.owner_kind != "session":
            raise ValueError("Conversation identity must be session-scoped.")
        try:
            return UUID(conversation_identity.owner_id)
        except ValueError as exc:
            raise ValueError("Conversation identity has an invalid session id.") from exc

    async def _load_scenario_context(
        self,
        *,
        session_id: UUID,
    ) -> "_ScenarioContext":
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            raise ValueError("Scenario session not found for conversation identity.")

        if session.owner_kind == "user":
            user = await self._user_identity_store.get_by_id(session.owner_id)
            if user is None:
                raise ValueError("User not found for scenario session.")
        elif session.owner_kind == "group":
            group = await self._group_identity_store.get_by_id(session.owner_id)
            if group is None:
                raise ValueError("Group not found for scenario session.")
            user = self._group_to_user(group)
        else:
            raise ValueError("Scenario session has an unsupported owner kind.")

        definition = await self._scenario_definition_store.get_by_id(
            session.scenario_definition_id
        )
        if definition is None:
            raise ValueError("Scenario definition not found for session.")

        active_character = ConversationBuilder.resolve_active_character(
            scenario=definition,
            session=session,
        )
        return _ScenarioContext(
            definition=definition,
            session=session,
            user=user,
            character=active_character,
            world=definition.world,
        )

    def _feedback_context(self, context: "_ScenarioContext") -> FeedbackContext:
        return FeedbackContext(
            conversation_owner_id=str(context.session.id),
            character_id=context.character.id if context.character is not None else "",
            character_name=context.character.name if context.character is not None else "",
            user_display_name=context.user.display_name,
            world_id=context.world.id if context.world is not None else "",
        )

    def _build_input(
        self,
        context: "_ScenarioContext",
        *,
        memory_messages: list[ConversationMessage],
        user_message: str,
    ) -> ScenarioConversationInput:
        return ScenarioConversationInput(
            scenario=context.definition,
            session=context.session,
            user=context.user,
            memory_messages=memory_messages,
            user_message=user_message,
        )

    @staticmethod
    def _group_to_user(group: Group) -> User:
        return User(id=group.id, display_name=group.display_name)

    @staticmethod
    def _should_resume(history: list[ConversationMessage]) -> bool:
        if not history:
            return False
        last = history[-1]
        return (
            last.role == ConversationRole.CHARACTER
            and last.metadata.get(FINISH_REASON_METADATA_KEY) == FINISH_REASON_LENGTH
        )

    @staticmethod
    def _narrator_message(llm_response: LLMResponse) -> ConversationMessage:
        """Build the stored narrator turn, recording why generation stopped.

        The finish reason lets `/continue` tell a truncated reply (``length``) from a
        naturally-ended one, so it can resume the cut-off text instead of advancing.
        """
        metadata: dict[str, str] = {}
        if llm_response.finish_reason:
            metadata[FINISH_REASON_METADATA_KEY] = llm_response.finish_reason
        return ConversationMessage(
            role=ConversationRole.CHARACTER,
            content=llm_response.content,
            metadata=metadata,
        )

    @staticmethod
    def _resolve_turn(history: list[ConversationMessage]) -> int:
        character_replies = sum(
            1 for message in history if message.role == ConversationRole.CHARACTER
        )
        return character_replies + 1

    @staticmethod
    def _to_latency_ms(started_at: float) -> int:
        return int(round((perf_counter() - started_at) * 1000))

    async def _append_generation_trace(
        self,
        *,
        session_id: UUID,
        turn: int,
        request_id: str,
        conversation: Conversation,
        generation_settings: GenerationSettings,
        memory_messages: list[ConversationMessage],
        response: LLMResponse | None,
        latency_ms: int,
        error: Exception | None = None,
    ) -> None:
        if self._generation_trace_store is None:
            return
        if self._generation_trace_mode == "off":
            return
        if self._generation_trace_mode == "errors" and error is None:
            return

        provider = "unknown"
        model = "unknown"
        usage: dict[str, int] = {}
        finish_reason = "error" if error is not None else "unknown"
        response_content = ""

        if response is not None:
            provider = response.metadata.get("provider", "unknown")
            model = response.metadata.get("model_name", "unknown")
            finish_reason = response.finish_reason
            response_content = response.content
            usage = self._extract_usage(response.metadata)

        prompt_payload = self._serialize_prompt(
            conversation=conversation,
            memory_messages=memory_messages,
        )
        prompt_stats = self._build_prompt_stats(
            prompt_payload=prompt_payload,
            conversation=conversation,
        )

        record: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "turn": turn,
            "request_id": request_id,
            "provider": provider,
            "model": model,
            "prompt": prompt_payload,
            "prompt_stats": prompt_stats,
            "messages": self._serialize_messages(conversation.messages),
            "generation": {
                "temperature": generation_settings.temperature,
                "top_p": generation_settings.top_p,
                "max_tokens": generation_settings.max_tokens,
                "seed": None,
                "stop_sequences": list(generation_settings.stop_sequences),
            },
            "response": response_content,
            "usage": usage,
            "finish_reason": finish_reason,
            "latency_ms": latency_ms,
        }
        if error is not None:
            record["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }

        try:
            await self._generation_trace_store.append(session_id=session_id, record=record)
        except Exception:
            logger.exception(
                "Failed to append generation trace",
                extra={"session_id": str(session_id)},
            )

    @staticmethod
    def _extract_usage(metadata: dict[str, str]) -> dict[str, int]:
        usage: dict[str, int] = {}
        mappings = {
            "prompt_tokens": "usage_prompt_tokens",
            "completion_tokens": "usage_completion_tokens",
            "total_tokens": "usage_total_tokens",
        }
        for usage_key, metadata_key in mappings.items():
            raw = metadata.get(metadata_key)
            if raw is None:
                continue
            try:
                usage[usage_key] = int(raw)
            except ValueError:
                continue
        return usage

    @staticmethod
    def _serialize_prompt(
        *,
        conversation: Conversation,
        memory_messages: list[ConversationMessage],
    ) -> dict[str, str]:
        system_messages = [
            message.content
            for message in conversation.messages
            if message.role == ConversationRole.SYSTEM
        ]
        character_prompt = system_messages[0] if len(system_messages) > 0 else ""
        world_prompt = system_messages[1] if len(system_messages) > 1 else ""
        conversation_rules = system_messages[2] if len(system_messages) > 2 else ""
        memory_snapshot = "\n".join(
            f"{message.role.value}: {message.content}" for message in memory_messages
        )
        assembled_system_prompt = "\n\n".join(system_messages)
        return {
            "character": character_prompt,
            "world": world_prompt,
            "memory": memory_snapshot,
            "conversation_rules": conversation_rules,
            "assembled_system_prompt": assembled_system_prompt,
        }

    @staticmethod
    def _serialize_messages(messages: list[ConversationMessage]) -> list[dict[str, object]]:
        payload: list[dict[str, object]] = []
        for message in messages:
            role = message.role.value
            if message.role == ConversationRole.CHARACTER:
                role = "assistant"
            payload.append(
                {
                    "role": role,
                    "content": message.content,
                    "metadata": message.metadata,
                }
            )
        return payload

    @classmethod
    def _build_prompt_stats(
        cls,
        *,
        prompt_payload: dict[str, str],
        conversation: Conversation,
    ) -> dict[str, int]:
        character_tokens = cls._estimate_tokens(prompt_payload.get("character", ""))
        world_tokens = cls._estimate_tokens(prompt_payload.get("world", ""))
        memory_tokens = cls._estimate_tokens(prompt_payload.get("memory", ""))
        system_tokens = cls._estimate_tokens(prompt_payload.get("assembled_system_prompt", ""))
        history_text = "\n".join(
            message.content
            for message in conversation.messages
            if message.role != ConversationRole.SYSTEM
        )
        history_tokens = cls._estimate_tokens(history_text)
        total_prompt_tokens = system_tokens + history_tokens
        return {
            "character_tokens": character_tokens,
            "world_tokens": world_tokens,
            "memory_tokens": memory_tokens,
            "history_tokens": history_tokens,
            "system_tokens": system_tokens,
            "total_prompt_tokens": total_prompt_tokens,
        }

    @staticmethod
    def _estimate_tokens(value: str) -> int:
        stripped = value.strip()
        if not stripped:
            return 0
        return len(stripped.split())

    @staticmethod
    def _find_latest_user_index(messages: list[ConversationMessage]) -> int | None:
        for index in range(len(messages) - 1, -1, -1):
            if messages[index].role == ConversationRole.USER:
                return index
        return None
