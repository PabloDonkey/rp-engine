import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.builder import (
    PROMPT_SECTION_CHARACTER,
    PROMPT_SECTION_MEMORY,
    PROMPT_SECTION_METADATA_KEY,
    PROMPT_SECTION_RESPONSE_FORMAT,
    PROMPT_SECTION_SCENARIO_RULES,
    PROMPT_SECTION_WORLD,
    ConversationBuilder,
    ScenarioConversationInput,
)
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import (
    FINISH_REASON_LENGTH,
    FINISH_REASON_METADATA_KEY,
    THINKING_METADATA_KEY,
    TURN_METADATA_KEY,
    ConversationMessage,
)
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.group.group import Group
from rp_engine.core.llm.errors import EmptyGenerationError
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.memory.pipeline import MemoryPipeline
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecall
from rp_engine.core.memory.recent_window_source import MESSAGE_OVERHEAD_TOKENS
from rp_engine.core.ports import (
    BackgroundTaskScheduler,
    ConversationStore,
    FeedbackContext,
    GenerationTraceStore,
    GroupIdentityStore,
    NoOpProcessingFeedback,
    ProcessingFeedback,
    ScenarioDefinitionStore,
    ScenarioSessionStore,
    TokenCounter,
    UserIdentityStore,
    processing_feedback_scope,
)
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

logger = logging.getLogger(__name__)

# The user turn sent when the player asks for more story without writing anything.
CONTINUE_MESSAGE = "continue"


class SessionBusyError(RuntimeError):
    """A generation is already running for this session.

    Two surfaces reach the same story: Telegram and the admin panel. Both call this
    service, in the same process, so one set of session ids is enough to keep them apart.
    That stops being true the moment the two surfaces run as separate processes — then this
    has to move into Postgres, and the failure it prevents comes back silently until it does.
    """


# Metadata keys live in the core (`core/conversation/message.py`) and are re-exported here
# so existing importers of `chat_service.FINISH_REASON_METADATA_KEY` keep working.
__all__ = [
    "FINISH_REASON_LENGTH",
    "FINISH_REASON_METADATA_KEY",
    "THINKING_METADATA_KEY",
    "TURN_METADATA_KEY",
    "ChatService",
]


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
        memory_pipeline: MemoryPipeline,
        token_counter: TokenCounter,
        user_identity_store: UserIdentityStore,
        group_identity_store: GroupIdentityStore,
        scenario_session_store: ScenarioSessionStore,
        scenario_definition_store: ScenarioDefinitionStore,
        generation_settings: GenerationSettings,
        generation_trace_store: GenerationTraceStore | None = None,
        generation_trace_mode: Literal["off", "errors", "all"] = "off",
        length_retry_settings: GenerationSettings | None = None,
        task_scheduler: BackgroundTaskScheduler | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._conversation_store = conversation_store
        self._memory_pipeline = memory_pipeline
        self._token_counter = token_counter
        self._user_identity_store = user_identity_store
        self._group_identity_store = group_identity_store
        self._scenario_session_store = scenario_session_store
        self._scenario_definition_store = scenario_definition_store
        self._generation_settings = generation_settings
        self._generation_trace_store = generation_trace_store
        self._generation_trace_mode = generation_trace_mode
        # Settings for the one automatic retry after a reply stops at the token cap. `None`
        # turns the recovery off, which is what every caller that does not care about it gets.
        self._length_retry_settings = length_retry_settings
        # Where the memory layers' write half runs. `None` means nothing observes turns,
        # which is what every caller that only reads memory gets.
        self._task_scheduler = task_scheduler
        # Sessions with a generation in flight. Refusing beats queueing: a second turn
        # started while the first is running would build its prompt from a history that is
        # about to change under it, and the player who sent it is owed an answer, not a
        # wait for a reply they did not ask for.
        self._generating_sessions: set[UUID] = set()
        self._conversation_builder = ConversationBuilder()

    @contextmanager
    def _one_generation_per_session(self, session_id: UUID) -> Iterator[None]:
        """Hold the right to generate for `session_id`, or refuse.

        There is no await between the check and the add, so a second coroutine cannot slip
        between them. `finally` matters more than it looks: a generation that raises must
        release, or the story is locked out until the process restarts.
        """
        if session_id in self._generating_sessions:
            raise SessionBusyError("This story is already writing a reply. Wait for it to finish.")
        self._generating_sessions.add(session_id)
        try:
            yield
        finally:
            self._generating_sessions.discard(session_id)

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
        with self._one_generation_per_session(session_id):
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
                recall = await self._recall(context, history=history, user_message=cleaned_message)
                context_messages = list(recall.messages)
                builder_input = self._build_input(
                    context,
                    recall=recall,
                    user_message=cleaned_message,
                )
                conversation = self._conversation_builder.build(builder_input)
                request = GenerationRequest(
                    memory_key=memory_key,
                    conversation=conversation,
                    settings=self._generation_settings,
                )
                turn = self._resolve_turn(history)
                resume_prefix, prefill_text = self._resume_anchor(
                    conversation=conversation,
                    context_messages=context_messages,
                    resumed=False,
                )

                llm_response = await self._generate_recovering_length(
                    request=request,
                    builder_input=builder_input,
                    resume_prefix=resume_prefix,
                    prefill_text=prefill_text,
                    session_id=session.id,
                    turn=turn,
                    memory_recall=recall,
                )
                # Guard before the trace-adjacent work below: the trace is already recorded (an
                # empty generation is exactly what you want a trace for), but nothing has been
                # persisted to the conversation and the director note is still unconsumed.
                self._require_content(llm_response)
                character_response = llm_response.content
            await self._consume_director_instruction(session)
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
                self._narrator_message(llm_response, turn),
            )
            self._observe_turn(context, turn=turn)
            return character_response

    async def continue_story(
        self,
        *,
        conversation_identity: ConversationIdentity,
        processing_feedback: ProcessingFeedback | None = None,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        with self._one_generation_per_session(session_id):
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
                recall = await self._recall(context, history=history, user_message=CONTINUE_MESSAGE)
                context_messages = list(recall.messages)
                builder_input = self._build_input(
                    context,
                    recall=recall,
                    user_message=CONTINUE_MESSAGE,
                )
                # If the last narrator reply was cut off at the token limit, resume it
                # in place; otherwise advance the story with no player input.
                resumed = self._should_resume(history)
                if resumed:
                    conversation = self._conversation_builder.build_resume(builder_input)
                else:
                    conversation = self._conversation_builder.build_continue(builder_input)
                request = GenerationRequest(
                    memory_key=memory_key,
                    conversation=conversation,
                    settings=self._generation_settings,
                )
                turn = self._resolve_turn(history)
                resume_prefix, prefill_text = self._resume_anchor(
                    conversation=conversation,
                    context_messages=context_messages,
                    resumed=resumed,
                )

                llm_response = await self._generate_recovering_length(
                    request=request,
                    builder_input=builder_input,
                    resume_prefix=resume_prefix,
                    prefill_text=prefill_text,
                    session_id=session.id,
                    turn=turn,
                    memory_recall=recall,
                )
                # Guard before the trace-adjacent work below: the trace is already recorded (an
                # empty generation is exactly what you want a trace for), but nothing has been
                # persisted to the conversation and the director note is still unconsumed.
                self._require_content(llm_response)
                character_response = llm_response.content
            await self._consume_director_instruction(session)
            await self._conversation_store.save_message(
                memory_key,
                self._narrator_message(llm_response, turn),
            )
            self._observe_turn(context, turn=turn)
            return character_response

    async def regenerate_last_response(
        self,
        *,
        conversation_identity: ConversationIdentity,
        processing_feedback: ProcessingFeedback | None = None,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        with self._one_generation_per_session(session_id):
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
                resumed = False
                if latest_context_message.role == ConversationRole.USER:
                    latest_user_index = self._find_latest_user_index(trimmed_history)
                    if latest_user_index is None:
                        raise ValueError("Conversation has no user message to regenerate from.")

                    last_user = trimmed_history[latest_user_index]
                    prior_history = trimmed_history[:latest_user_index]
                    recall = await self._recall(
                        context, history=prior_history, user_message=last_user.content
                    )
                    context_messages = list(recall.messages)
                    builder_input = self._build_input(
                        context,
                        recall=recall,
                        user_message=last_user.content,
                    )
                    conversation = self._conversation_builder.build(builder_input)
                elif latest_context_message.role == ConversationRole.CHARACTER:
                    recall = await self._recall(
                        context, history=trimmed_history, user_message=CONTINUE_MESSAGE
                    )
                    context_messages = list(recall.messages)
                    builder_input = self._build_input(
                        context,
                        recall=recall,
                        user_message=CONTINUE_MESSAGE,
                    )
                    # Mirror `continue_story`: once the failed turn is dropped, whatever is now
                    # last decides the mode. Retrying a resume must resume again — advancing
                    # instead would strand the cut-off sentence permanently, since the turn that
                    # would have finished it is the one being replaced.
                    resumed = self._should_resume(trimmed_history)
                    if resumed:
                        conversation = self._conversation_builder.build_resume(builder_input)
                    else:
                        conversation = self._conversation_builder.build_continue(builder_input)
                else:
                    raise ValueError("Conversation has no valid context to regenerate from.")
                request = GenerationRequest(
                    memory_key=memory_key,
                    conversation=conversation,
                    settings=self._generation_settings,
                )
                turn = self._resolve_turn(trimmed_history)
                resume_prefix, prefill_text = self._resume_anchor(
                    conversation=conversation,
                    context_messages=context_messages,
                    resumed=resumed,
                )

                llm_response = await self._generate_recovering_length(
                    request=request,
                    builder_input=builder_input,
                    resume_prefix=resume_prefix,
                    prefill_text=prefill_text,
                    session_id=session.id,
                    turn=turn,
                    memory_recall=recall,
                )
                # Must precede the `clear()` below — a retry that came back empty must not cost
                # the player the history it was regenerating from.
                self._require_content(llm_response)
                character_response = llm_response.content

            await self._consume_director_instruction(session)
            await self._conversation_store.clear(memory_key)
            for message in trimmed_history:
                await self._conversation_store.save_message(memory_key, message)
            await self._conversation_store.save_message(
                memory_key,
                self._narrator_message(llm_response, turn),
            )
            self._observe_turn(context, turn=turn)
            return character_response

    async def _generate_traced(
        self,
        *,
        request: GenerationRequest,
        session_id: UUID,
        turn: int,
        memory_recall: MemoryRecall,
    ) -> LLMResponse:
        """Run one generation and record its trace, whether it succeeded or failed."""
        request_id = str(uuid4())
        started_at = perf_counter()
        try:
            llm_response = await self._orchestrator.generate_reply(request)
        except Exception as exc:
            await self._append_generation_trace(
                session_id=session_id,
                turn=turn,
                request_id=request_id,
                conversation=request.conversation,
                generation_settings=request.settings,
                memory_recall=memory_recall,
                response=None,
                latency_ms=self._to_latency_ms(started_at),
                error=exc,
            )
            raise

        await self._append_generation_trace(
            session_id=session_id,
            turn=turn,
            request_id=request_id,
            conversation=request.conversation,
            generation_settings=request.settings,
            memory_recall=memory_recall,
            response=llm_response,
            latency_ms=self._to_latency_ms(started_at),
        )
        return llm_response

    async def _generate_recovering_length(
        self,
        *,
        request: GenerationRequest,
        builder_input: ScenarioConversationInput,
        resume_prefix: list[ConversationMessage],
        prefill_text: str,
        session_id: UUID,
        turn: int,
        memory_recall: MemoryRecall,
    ) -> LLMResponse:
        """Generate a reply, recovering once from the model's own token cap.

        `finish_reason: length` means the model was cut off, and the player is left holding
        half a turn — or, with a reasoning model, no turn at all. One extra attempt fixes
        both cases, and the two need different shapes:

        - Some prose was written. Resume it as an assistant prefill so the model continues
          from those exact tokens, and hand back both halves as one reply.
        - Nothing was written, because reasoning consumed the whole budget. There is nothing
          to prefill, so re-run the original request. Only the larger retry cap makes the
          second attempt different from the first.

        `context_length` is deliberately not recovered: the context window is full, so a
        second attempt would hit the same wall. Only one retry is made — if the cap is hit
        again the reply is still stored as truncated, so `/continue` can carry on by hand.
        """
        response = await self._generate_traced(
            request=request,
            session_id=session_id,
            turn=turn,
            memory_recall=memory_recall,
        )
        retry_settings = self._length_retry_settings
        if retry_settings is None or response.finish_reason != FINISH_REASON_LENGTH:
            return response

        # Everything written for this reply so far, including any earlier truncated text the
        # request was already resuming — that is what the model must continue from.
        carried = prefill_text + response.content
        resumable = bool(carried.strip())
        # Mode and cap go in the message, not only in `extra`: the default log format renders
        # `%(message)s` and drops the extra fields.
        logger.info(
            "Reply stopped at the token cap; retrying once (mode=%s, max_tokens=%s)",
            "resume" if resumable else "regenerate",
            retry_settings.max_tokens,
            extra={
                "session_id": str(session_id),
                "turn": turn,
                "mode": "resume" if resumable else "regenerate",
                "retry_max_tokens": retry_settings.max_tokens,
            },
        )
        if resumable:
            retry_conversation = self._conversation_builder.build_resume(
                replace(
                    builder_input,
                    memory_messages=[
                        *resume_prefix,
                        ConversationMessage(role=ConversationRole.CHARACTER, content=carried),
                    ],
                )
            )
        else:
            retry_conversation = request.conversation

        retry_response = await self._generate_traced(
            request=GenerationRequest(
                memory_key=request.memory_key,
                conversation=retry_conversation,
                settings=retry_settings,
            ),
            session_id=session_id,
            turn=turn,
            memory_recall=memory_recall,
        )
        if not resumable:
            return retry_response
        # A prefill continuation normally emits no reasoning of its own, so keep the thinking
        # from the attempt that did the planning rather than dropping it.
        return replace(
            retry_response,
            content=response.content + retry_response.content,
            thinking=retry_response.thinking or response.thinking,
        )

    @staticmethod
    def _resume_anchor(
        *,
        conversation: Conversation,
        context_messages: list[ConversationMessage],
        resumed: bool,
    ) -> tuple[list[ConversationMessage], str]:
        """Where an automatic resume has to pick the reply up from.

        A prefill conversation already ends with truncated text, so that text is the start
        of the same reply and the messages before it are the prefix. Any other conversation
        ends with the turn that asked for a reply, and the reply starts empty.

        `resumed` is decided from the stored history, while the prefill itself comes from
        what the memory strategy kept. A strategy that dropped the truncated turn would make
        those two disagree — `build_resume` is already wrong in that case, and the provider
        warns about it, so treat it as "nothing to carry" rather than crash the turn.
        """
        if resumed and context_messages:
            return context_messages[:-1], context_messages[-1].content
        return [*context_messages, conversation.messages[-1]], ""

    @staticmethod
    def _require_content(llm_response: LLMResponse) -> None:
        """Reject a reply with no usable text before anything is persisted.

        A reasoning model can burn its entire token budget thinking and stop before writing
        any prose, which arrives here as empty content (the reasoning itself is captured
        separately as `thinking`). Storing that would put an empty narrator turn into the
        history — replayed into every later prompt, counted as a turn, and, when it carries
        `finish_reason: length`, enough to make the next `/continue` try to resume nothing
        and produce another empty turn. Raising instead leaves the conversation exactly as
        it was, so the player can simply try again.
        """
        if llm_response.content.strip():
            return
        raise EmptyGenerationError(
            "The model returned an empty reply.",
            finish_reason=llm_response.finish_reason,
        )

    async def _consume_director_instruction(self, session: ScenarioSession) -> None:
        """Clear the one-turn director notes that the generation just consumed.

        Called only after a *successful* generation, so a failed turn keeps the queue
        alive for the retry the player is about to make. The notes are cleared as a unit:
        they all applied to the same reply, so none of them outlives it.
        """
        directives = session.directives
        if not directives.has_director_instructions:
            return
        await self._scenario_session_store.save(
            session.with_directives(directives.without_director_instructions())
        )

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

        definition = await self._scenario_definition_store.get_by_id(session.scenario_definition_id)
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
        recall: MemoryRecall,
        user_message: str,
    ) -> ScenarioConversationInput:
        return ScenarioConversationInput(
            scenario=context.definition,
            session=context.session,
            user=context.user,
            memory_messages=list(recall.messages),
            user_message=user_message,
            memory_fragments=recall.fragments,
        )

    async def _recall(
        self,
        context: "_ScenarioContext",
        *,
        history: list[ConversationMessage],
        user_message: str,
    ) -> MemoryRecall:
        """Ask the memory layers what this turn's prompt should carry.

        The prompt is built twice. The first build has no memory in it at all, and exists
        only to price everything memory has to share the window with — the character card,
        the world, the session rules, the message the player just sent. Memory then gets
        what is left.

        Pricing it rather than reserving a fixed slice is what keeps the budget honest: a
        scenario with a long card and ten session rules leaves less room for history than
        a bare one, and no constant can know that. The second build is cheap (the builder
        is pure string work) and the token counts behind it are cached per text, so the
        static sections are counted once and read from the cache on every later turn.
        """
        priced = self._conversation_builder.build(
            self._build_input(context, recall=MemoryRecall(), user_message=user_message)
        )
        reserved = await self._count_tokens(priced.messages)
        return await self._memory_pipeline.recall(
            session_id=context.session.id,
            scenario_definition_id=context.definition.id,
            messages=history,
            current_user_message=user_message,
            reserved_tokens=reserved,
            settings=context.session.memory,
        )

    def _observe_turn(self, context: "_ScenarioContext", *, turn: int) -> None:
        """Ask the memory layers to catch up, off the turn path.

        This is the one place the write half is started (ADR-026 decision 1): the scheduler
        wraps `MemoryPipeline.observe` here, so no memory source knows that background
        execution exists. It returns as soon as the question is queued, and the answer
        never reaches the player — a layer that fails, or a job dropped by a full queue or
        a restart, costs nothing, because the next turn asks the same question.

        One key per session, not per layer: the pipeline runs every enabled layer in one
        job, so two fast turns of the same session must collapse into one pass rather than
        two writers racing over the same rows.
        """
        scheduler = self._task_scheduler
        if scheduler is None:
            return
        observe_context = MemoryObserveContext(
            session_id=context.session.id,
            scenario_definition_id=context.definition.id,
            turn=turn,
        )
        settings = context.session.memory

        async def job() -> None:
            await self._memory_pipeline.observe(observe_context, settings=settings)

        scheduler.submit(key=f"memory:{context.session.id}", job=job)

    async def _count_tokens(self, messages: list[ConversationMessage]) -> int:
        total = 0
        for message in messages:
            total += await self._token_counter.count_tokens(message.content)
            total += MESSAGE_OVERHEAD_TOKENS
        return total

    @staticmethod
    def _group_to_user(group: Group) -> User:
        return User(id=group.id, display_name=group.display_name)

    @staticmethod
    def _should_resume(history: list[ConversationMessage]) -> bool:
        if not history:
            return False
        last = history[-1]
        return last.role == ConversationRole.CHARACTER and last.was_truncated

    @staticmethod
    def _narrator_message(llm_response: LLMResponse, turn: int) -> ConversationMessage:
        """Build the stored narrator turn, recording why generation stopped.

        The finish reason lets `/continue` tell a truncated reply (``length``) from a
        naturally-ended one, so it can resume the cut-off text instead of advancing. The
        turn number and any captured thinking ride along so the admin transcript can
        render them per-message without cross-referencing the generation trace.
        """
        metadata: dict[str, str] = {TURN_METADATA_KEY: str(turn)}
        if llm_response.finish_reason:
            metadata[FINISH_REASON_METADATA_KEY] = llm_response.finish_reason
        if llm_response.thinking:
            metadata[THINKING_METADATA_KEY] = llm_response.thinking
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
        memory_recall: MemoryRecall,
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
        thinking: str | None = None

        if response is not None:
            provider = response.metadata.get("provider", "unknown")
            model = response.metadata.get("model_name", "unknown")
            finish_reason = response.finish_reason
            response_content = response.content
            usage = self._extract_usage(response.metadata)
            thinking = response.thinking

        prompt_payload = self._serialize_prompt(
            conversation=conversation,
            memory_messages=list(memory_recall.messages),
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
            "thinking": thinking,
            "usage": usage,
            "finish_reason": finish_reason,
            "latency_ms": latency_ms,
            # What the context budget could not hold. This is the only place it is
            # recorded (ADR-026): the player is not told, and there is no per-turn log
            # line, because with layer 01 off it happens on every turn of every long
            # session and a warning that always fires is a warning nobody reads.
            "memory": memory_recall.to_trace_record(),
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
            message for message in conversation.messages if message.role == ConversationRole.SYSTEM
        ]
        # By label, never by position. Every section the builder adds shifts the one after
        # it, and this read was already returning the wrong three sections before the
        # memory section was added to the end of the list.
        sections = {
            message.metadata.get(PROMPT_SECTION_METADATA_KEY, ""): message.content
            for message in system_messages
        }
        memory_snapshot = "\n".join(
            f"{message.role.value}: {message.content}" for message in memory_messages
        )
        assembled_system_prompt = "\n\n".join(message.content for message in system_messages)
        return {
            "character": sections.get(PROMPT_SECTION_CHARACTER, ""),
            "world": sections.get(PROMPT_SECTION_WORLD, ""),
            # The replayed turns, not the memory section: this key has always held the
            # history the prompt carried, and the admin transcript reads it that way.
            "memory": memory_snapshot,
            "memory_section": sections.get(PROMPT_SECTION_MEMORY, ""),
            "scenario_rules": sections.get(PROMPT_SECTION_SCENARIO_RULES, ""),
            # The engine's own reply contract. It is what slot 2 held back when the
            # sections were read positionally.
            "conversation_rules": sections.get(PROMPT_SECTION_RESPONSE_FORMAT, ""),
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
