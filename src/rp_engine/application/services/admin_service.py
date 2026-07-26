from dataclasses import dataclass
from uuid import UUID

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.generation_trace_store import GenerationTraceStore
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.ports.user_identity_store import UserIdentityStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    user: User
    session_count: int


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
    ) -> None:
        self._user_identity_store = user_identity_store
        self._scenario_session_store = scenario_session_store
        self._conversation_store = conversation_store
        self._generation_trace_store = generation_trace_store
        self._scenario_definition_store = scenario_definition_store

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
        return await self._scenario_session_store.find_by_owner("user", user_id)

    async def get_session(self, session_id: UUID) -> ScenarioSession | None:
        return await self._scenario_session_store.get_by_id(session_id)

    async def get_session_transcript(self, session_id: UUID) -> list[ConversationMessage]:
        memory_key = ConversationIdentity.for_session(str(session_id)).to_memory_key()
        return await self._conversation_store.load_messages(memory_key)

    async def get_session_traces(self, session_id: UUID) -> list[dict[str, object]]:
        return await self._generation_trace_store.list_for_session(session_id)

    async def delete_session(self, session_id: UUID) -> None:
        memory_key = ConversationIdentity.for_session(str(session_id)).to_memory_key()
        await self._conversation_store.clear(memory_key)
        await self._scenario_session_store.delete(session_id)

    async def list_scenarios(self) -> list[ScenarioDefinition]:
        scenarios = await self._scenario_definition_store.find_by_owner(SYSTEM_OWNER_ID)
        return sorted(scenarios, key=lambda scenario: scenario.name.lower())

    async def get_scenario(self, scenario_id: str) -> ScenarioDefinition | None:
        return await self._scenario_definition_store.get_by_id(scenario_id)
