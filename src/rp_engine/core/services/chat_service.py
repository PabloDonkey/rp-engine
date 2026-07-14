import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.builder import ConversationBuilder, ConversationBuilderInput
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
    CharacterStore,
    ConversationStore,
    FeedbackContext,
    GenerationTraceStore,
    GroupIdentityStore,
    MemoryStrategy,
    NoOpProcessingFeedback,
    ProcessingFeedback,
    SessionStore,
    UserIdentityStore,
    WorldStore,
    processing_feedback_scope,
)
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        orchestrator: RPOrchestrator,
        conversation_store: ConversationStore,
        memory_strategy: MemoryStrategy,
        user_identity_store: UserIdentityStore,
        group_identity_store: GroupIdentityStore,
        session_store: SessionStore,
        character_store: CharacterStore,
        world_store: WorldStore,
        generation_settings: GenerationSettings,
        generation_trace_store: GenerationTraceStore | None = None,
        generation_trace_mode: Literal["off", "errors", "all"] = "off",
    ) -> None:
        self._orchestrator = orchestrator
        self._conversation_store = conversation_store
        self._memory_strategy = memory_strategy
        self._user_identity_store = user_identity_store
        self._group_identity_store = group_identity_store
        self._session_store = session_store
        self._character_store = character_store
        self._world_store = world_store
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

        session, owner_user, character, world = await self._load_conversation_context(
            session_id=session_id
        )
        feedback = processing_feedback or NoOpProcessingFeedback()
        feedback_context = FeedbackContext(
            conversation_owner_id=str(session.id),
            character_id=character.id,
            character_name=character.name,
            user_display_name=owner_user.display_name,
            world_id=world.id,
        )
        async with processing_feedback_scope(feedback, context=feedback_context):
            history = await self._conversation_store.load_messages(memory_key)
            context_messages = self._memory_strategy.build_context(history)
            conversation = self._conversation_builder.build(
                ConversationBuilderInput(
                    session=session,
                    user=owner_user,
                    character=character,
                    world=world,
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
            ConversationMessage(role=ConversationRole.CHARACTER, content=character_response),
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
        session, owner_user, character, world = await self._load_conversation_context(
            session_id=session_id
        )
        feedback = processing_feedback or NoOpProcessingFeedback()
        feedback_context = FeedbackContext(
            conversation_owner_id=str(session.id),
            character_id=character.id,
            character_name=character.name,
            user_display_name=owner_user.display_name,
            world_id=world.id,
        )
        async with processing_feedback_scope(feedback, context=feedback_context):
            history = await self._conversation_store.load_messages(memory_key)
            context_messages = self._memory_strategy.build_context(history)
            conversation = self._conversation_builder.build_continue(
                ConversationBuilderInput(
                    session=session,
                    user=owner_user,
                    character=character,
                    world=world,
                    memory_messages=context_messages,
                    user_message="continue",
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
            ConversationMessage(role=ConversationRole.CHARACTER, content=character_response),
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

    async def _load_conversation_context(
        self,
        *,
        session_id: UUID,
    ) -> tuple[Session, User, Character, World]:
        session = await self._session_store.get_by_id(session_id)
        if session is None:
            raise ValueError("Session not found for conversation identity.")

        if session.owner_kind == "user":
            user = await self._user_identity_store.get_by_id(session.owner_id)
            if user is None:
                raise ValueError("User not found for session.")
        elif session.owner_kind == "group":
            group = await self._group_identity_store.get_by_id(session.owner_id)
            if group is None:
                raise ValueError("Group not found for session.")
            user = self._group_to_user(group)
        else:
            raise ValueError("Session has an unsupported owner kind.")

        character = await self._character_store.get_by_id(session.character_id)
        if character is None:
            raise ValueError("Character not found for session.")

        world = await self._world_store.get_by_id(session.world_id)
        if world is None:
            raise ValueError("World not found for session.")

        return session, user, character, world

    @staticmethod
    def _group_to_user(group: Group) -> User:
        return User(id=group.id, display_name=group.display_name)

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
