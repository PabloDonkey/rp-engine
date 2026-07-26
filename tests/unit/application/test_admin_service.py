from uuid import UUID

import pytest

from rp_engine.application.services.admin_service import AdminService
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID

USER_ID = UUID("00000000-0000-0000-0000-000000000042")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000043")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000999")


class FakeUserIdentityStore:
    def __init__(self, users: list[User]) -> None:
        self._users = {user.id: user for user in users}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def get_user_by_identity(self, *, provider: str, external_id: str) -> User | None:
        raise NotImplementedError

    async def list_users(self) -> list[User]:
        return list(self._users.values())

    async def create_user_with_identity(self, *, display_name: str, identity: UserIdentity) -> User:
        raise NotImplementedError


class FakeScenarioSessionStore:
    def __init__(self, sessions: list[ScenarioSession]) -> None:
        self.sessions = {session.id: session for session in sessions}
        self.deleted: list[UUID] = []

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        return self.sessions.get(session_id)

    async def find_by_owner(self, owner_kind: str, owner_id: UUID) -> list[ScenarioSession]:
        return [
            s
            for s in self.sessions.values()
            if s.owner_kind == owner_kind and s.owner_id == owner_id
        ]

    async def find_by_definition(
        self, *, owner_kind: str, owner_id: UUID, scenario_definition_id: str
    ) -> ScenarioSession | None:
        raise NotImplementedError

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        self.sessions[session.id] = session
        return session

    async def delete(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)
        self.deleted.append(session_id)

    async def set_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID, session_id: UUID
    ) -> None:
        raise NotImplementedError

    async def get_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID
    ) -> ScenarioSession | None:
        raise NotImplementedError


class FakeConversationStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[ConversationMessage]] = {}

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        self._messages.setdefault(memory_key.value, []).append(message)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self._messages.get(memory_key.value, []))

    async def clear(self, memory_key: MemoryKey) -> None:
        self._messages.pop(memory_key.value, None)


class FakeGenerationTraceStore:
    def __init__(self) -> None:
        self._records: dict[UUID, list[dict[str, object]]] = {}

    async def append(self, *, session_id: UUID, record: dict[str, object]) -> None:
        self._records.setdefault(session_id, []).append(record)

    async def list_for_session(self, session_id: UUID) -> list[dict[str, object]]:
        return list(self._records.get(session_id, []))


class FakeScenarioDefinitionStore:
    def __init__(self, scenarios: list[ScenarioDefinition] | None = None) -> None:
        self.items = {scenario.id: scenario for scenario in scenarios or []}

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        return self.items.get(scenario_id)

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        return [s for s in self.items.values() if s.owner_id == owner_id]

    async def save(self, scenario: ScenarioDefinition) -> None:
        self.items[scenario.id] = scenario

    async def delete(self, scenario_id: str) -> None:
        self.items.pop(scenario_id, None)


def _session(*, owner_id: UUID = USER_ID) -> ScenarioSession:
    return ScenarioSession(
        id=SESSION_ID,
        scenario_definition_id="def-1",
        owner_kind="user",
        owner_id=owner_id,
    )


def _service(
    *,
    users: list[User] | None = None,
    sessions: list[ScenarioSession] | None = None,
    conversation_store: FakeConversationStore | None = None,
    trace_store: FakeGenerationTraceStore | None = None,
    scenarios: list[ScenarioDefinition] | None = None,
) -> tuple[AdminService, FakeScenarioSessionStore, FakeConversationStore, FakeGenerationTraceStore]:
    session_store = FakeScenarioSessionStore(sessions or [])
    convo_store = conversation_store or FakeConversationStore()
    traces = trace_store or FakeGenerationTraceStore()
    service = AdminService(
        user_identity_store=FakeUserIdentityStore(users or []),
        scenario_session_store=session_store,
        conversation_store=convo_store,
        generation_trace_store=traces,
        scenario_definition_store=FakeScenarioDefinitionStore(scenarios),
    )
    return service, session_store, convo_store, traces


@pytest.mark.asyncio
async def test_list_users_reports_session_counts() -> None:
    user = User(id=USER_ID, display_name="Pablo")
    other = User(id=OTHER_USER_ID, display_name="Nobody")
    service, _, _, _ = _service(users=[user, other], sessions=[_session(owner_id=USER_ID)])

    summaries = await service.list_users()

    by_id = {summary.user.id: summary.session_count for summary in summaries}
    assert by_id == {USER_ID: 1, OTHER_USER_ID: 0}


@pytest.mark.asyncio
async def test_list_user_sessions_filters_by_owner() -> None:
    service, _, _, _ = _service(sessions=[_session(owner_id=USER_ID)])

    sessions = await service.list_user_sessions(USER_ID)
    assert [s.id for s in sessions] == [SESSION_ID]

    assert await service.list_user_sessions(OTHER_USER_ID) == []


@pytest.mark.asyncio
async def test_get_session_transcript_and_traces() -> None:
    convo_store = FakeConversationStore()
    trace_store = FakeGenerationTraceStore()
    memory_key = ConversationIdentity.for_session(str(SESSION_ID)).to_memory_key()
    await convo_store.save_message(
        memory_key, ConversationMessage(role=ConversationRole.USER, content="hi")
    )
    await trace_store.append(session_id=SESSION_ID, record={"turn": 1})

    service, _, _, _ = _service(
        sessions=[_session()], conversation_store=convo_store, trace_store=trace_store
    )

    transcript = await service.get_session_transcript(SESSION_ID)
    assert [m.content for m in transcript] == ["hi"]

    traces = await service.get_session_traces(SESSION_ID)
    assert traces == [{"turn": 1}]


@pytest.mark.asyncio
async def test_delete_session_clears_session_and_conversation() -> None:
    convo_store = FakeConversationStore()
    memory_key = ConversationIdentity.for_session(str(SESSION_ID)).to_memory_key()
    await convo_store.save_message(
        memory_key, ConversationMessage(role=ConversationRole.USER, content="hi")
    )
    service, session_store, _, _ = _service(sessions=[_session()], conversation_store=convo_store)

    await service.delete_session(SESSION_ID)

    assert session_store.deleted == [SESSION_ID]
    assert await service.get_session(SESSION_ID) is None
    assert await convo_store.load_messages(memory_key) == []


def _scenario(scenario_id: str, *, name: str) -> ScenarioDefinition:
    return ScenarioDefinition(
        id=scenario_id, owner_id=SYSTEM_OWNER_ID, name=name, description=""
    )


@pytest.mark.asyncio
async def test_list_scenarios_sorted_by_name() -> None:
    service, _, _, _ = _service(
        scenarios=[_scenario("b", name="Zephyr"), _scenario("a", name="Aurora")]
    )

    scenarios = await service.list_scenarios()

    assert [s.name for s in scenarios] == ["Aurora", "Zephyr"]


@pytest.mark.asyncio
async def test_get_scenario_returns_none_when_missing() -> None:
    service, _, _, _ = _service(scenarios=[])

    assert await service.get_scenario("nope") is None
