import logging
from dataclasses import dataclass
from uuid import UUID

from rp_engine.core.conversation.message import TURN_METADATA_KEY, ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.context_budget import ContextBudget
from rp_engine.core.memory.fragment import ToggleableMemorySystemId
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.memory.recall_context import MemoryObserveContext
from rp_engine.core.memory.rolling_summary_source import RollingSummarySource, RollingSummaryStatus
from rp_engine.core.memory.session_summary import SessionSummary
from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.generation_trace_store import GenerationTraceStore
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.ports.session_summary_store import SessionSummaryStore
from rp_engine.core.ports.user_identity_store import UserIdentityStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    user: User
    session_count: int


@dataclass(frozen=True, slots=True)
class AdminSessionMemory:
    """Everything the panel shows about one session's memory, read in one call.

    The three parts answer three different questions: which layers run, how close the story
    is to its next recap, and what the recap currently says.
    """

    settings: MemorySettings
    status: RollingSummaryStatus
    summary: SessionSummary | None


@dataclass(frozen=True, slots=True)
class AdminDeletedMessage:
    """What a delete removed: the message, and how many of its traces went with it."""

    message: ConversationMessage
    deleted_traces: int


class AdminService:
    """Read/administer live scenario state: users, sessions, transcripts, traces.

    Backs the admin panel (debugging + basic moderation). Depends only on core ports so it
    stays backend-agnostic (JSON/Postgres), per the hexagonal layering in `docs/ARCHITECTURE.md`.
    """

    def __init__(
        self,
        *,
        user_identity_store: UserIdentityStore,
        scenario_session_store: ScenarioSessionStore,
        conversation_store: ConversationStore,
        generation_trace_store: GenerationTraceStore,
        scenario_definition_store: ScenarioDefinitionStore,
        session_summary_store: SessionSummaryStore,
        rolling_summary_source: RollingSummarySource,
        context_budget: ContextBudget,
    ) -> None:
        self._user_identity_store = user_identity_store
        self._scenario_session_store = scenario_session_store
        self._conversation_store = conversation_store
        self._generation_trace_store = generation_trace_store
        self._scenario_definition_store = scenario_definition_store
        self._session_summary_store = session_summary_store
        self._rolling_summary_source = rolling_summary_source
        self._context_budget = context_budget

    async def list_users(self) -> list[AdminUserSummary]:
        users = await self._user_identity_store.list_users()
        summaries = []
        for user in users:
            sessions = await self._scenario_session_store.find_by_owner("user", user.id)
            summaries.append(AdminUserSummary(user=user, session_count=len(sessions)))
        return summaries

    async def get_user(self, user_id: UUID) -> User | None:
        return await self._user_identity_store.get_by_id(user_id)

    async def list_user_sessions(self, user_id: UUID) -> list[ScenarioSession]:
        # The panel exists to debug playthroughs, so it opts into the superseded sessions
        # the engine hides — a restart's predecessor and its transcript are often exactly
        # what you came to read. `session_count` on the users list stays live-only.
        return await self._scenario_session_store.find_by_owner(
            "user", user_id, include_deleted=True
        )

    async def get_session(self, session_id: UUID) -> ScenarioSession | None:
        return await self._scenario_session_store.get_by_id(session_id)

    async def set_session_persona(
        self,
        session_id: UUID,
        *,
        name: str,
        description: str = "",
    ) -> ScenarioSession | None:
        """Set or replace a session's persona; None when the session is missing.

        Uses `override_persona`, the operator transition: the panel can both fill a gap
        (sessions that started before personas existed) and correct a persona already in
        place. Players keep the set-once contract — `/clear` remains their only way to
        change one — because they never reach this path.
        """
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            return None
        return await self._scenario_session_store.save(
            session.override_persona(name=name, description=description)
        )

    async def set_session_memory_source(
        self,
        session_id: UUID,
        *,
        source_id: ToggleableMemorySystemId,
        enabled: bool,
    ) -> ScenarioSession | None:
        """Switch one memory layer on or off for a session; None when it is missing.

        Layer 00 is not reachable here, and not because of a check: the parameter type does
        not contain it (ADR-026 rule 5).
        """
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            return None
        memory = (
            session.memory.with_source_enabled(source_id)
            if enabled
            else session.memory.with_source_disabled(source_id)
        )
        return await self._scenario_session_store.save(session.with_memory(memory))

    async def get_session_memory(self, session_id: UUID) -> AdminSessionMemory | None:
        """What the panel shows for memory; None when the session is missing.

        The status is measured the way the background worker measures it, so the panel and
        the worker cannot disagree about when the next recap is due.
        """
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            return None
        budget = await self._context_budget.total_tokens()
        return AdminSessionMemory(
            settings=session.memory,
            status=await self._rolling_summary_source.status(
                session_id=session_id,
                memory_budget=budget,
                source_budget=session.memory.budget_for("rolling_summary", budget),
            ),
            summary=await self._session_summary_store.get(session_id),
        )

    async def refresh_session_summary(self, session_id: UUID) -> AdminSessionMemory | None:
        """Run the rolling-summary pass now and report what it left behind.

        The same question the background worker asks after every turn, asked by a person
        instead. It runs **inline**, so this call lasts as long as one model call when there
        is something to fold, and returns at once when there is not.

        It runs even when the session has the layer switched off. An operator who wants to
        read a recap before deciding whether to switch the layer on should be able to make
        one.
        """
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            return None
        budget = await self._context_budget.total_tokens()
        await self._rolling_summary_source.observe(
            MemoryObserveContext(
                session_id=session_id,
                scenario_definition_id=session.scenario_definition_id,
                turn=self._narrator_turns(await self.get_session_transcript(session_id)),
                memory_budget=budget,
                source_budget=session.memory.budget_for("rolling_summary", budget),
            )
        )
        return await self.get_session_memory(session_id)

    @staticmethod
    def _narrator_turns(transcript: list[ConversationMessage]) -> int:
        return sum(1 for message in transcript if message.role == ConversationRole.CHARACTER)

    async def get_session_transcript(self, session_id: UUID) -> list[ConversationMessage]:
        memory_key = ConversationIdentity.for_session(str(session_id)).to_memory_key()
        return await self._conversation_store.load_messages(memory_key)

    async def get_session_traces(self, session_id: UUID) -> list[dict[str, object]]:
        return await self._generation_trace_store.list_for_session(session_id)

    async def delete_last_message(self, session_id: UUID) -> AdminDeletedMessage | None:
        """Peel the newest message off a session's transcript, with its generation traces.

        Last-only by design: a conversation is an ordered narrative, so removing from the
        middle would leave replies answering messages that no longer exist. Undoing a bad
        stretch means deleting repeatedly from the end.

        Traces go with the message. They describe how a turn was produced, so once that turn
        is gone they describe nothing — and leaving them would let the admin panel attach a
        stale trace to whatever message inherits the turn number. Only narrator replies carry
        a turn, so a deleted player message removes no traces.
        """
        memory_key = ConversationIdentity.for_session(str(session_id)).to_memory_key()
        deleted = await self._conversation_store.delete_last_message(memory_key)
        if deleted is None:
            return None

        deleted_traces = 0
        raw_turn = deleted.metadata.get(TURN_METADATA_KEY)
        if raw_turn is not None:
            try:
                turn = int(raw_turn)
            except ValueError:
                logger.warning(
                    "Deleted message has a non-numeric turn; leaving its traces in place",
                    extra={"session_id": str(session_id), "turn": raw_turn},
                )
            else:
                deleted_traces = await self._generation_trace_store.delete_for_turn(
                    session_id=session_id, turn=turn
                )
        return AdminDeletedMessage(message=deleted, deleted_traces=deleted_traces)

    async def delete_session(self, session_id: UUID) -> None:
        memory_key = ConversationIdentity.for_session(str(session_id)).to_memory_key()
        await self._conversation_store.clear(memory_key)
        await self._scenario_session_store.delete(session_id)

    async def list_scenarios(self) -> list[ScenarioDefinition]:
        scenarios = await self._scenario_definition_store.list_all()
        return sorted(scenarios, key=lambda scenario: scenario.name.lower())

    async def get_scenario(self, scenario_id: str) -> ScenarioDefinition | None:
        return await self._scenario_definition_store.get_by_id(scenario_id)
