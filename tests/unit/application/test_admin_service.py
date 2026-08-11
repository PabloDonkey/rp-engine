from uuid import UUID, uuid4

import pytest

from rp_engine.application.services.admin_service import AdminService
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.memory.session_summary import SessionSummary
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

    async def find_by_owner(
        self, owner_kind: str, owner_id: UUID, *, include_deleted: bool = False
    ) -> list[ScenarioSession]:
        return [
            s
            for s in self.sessions.values()
            if s.owner_kind == owner_kind
            and s.owner_id == owner_id
            and (include_deleted or not s.is_deleted)
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


class FakeSessionSummaryStore:
    def __init__(self, summary: SessionSummary | None = None) -> None:
        self.summary = summary

    async def get(self, session_id: UUID) -> SessionSummary | None:
        return self.summary

    async def save(self, summary: SessionSummary) -> SessionSummary:
        self.summary = summary
        return summary


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

    async def list_all(self) -> list[ScenarioDefinition]:
        return list(self.items.values())

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
        session_summary_store=FakeSessionSummaryStore(),
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


@pytest.mark.asyncio
async def test_set_session_persona_saves_it_on_a_session_without_one() -> None:
    session = _session(owner_id=USER_ID)
    service, session_store, _, _ = _service(sessions=[session])

    updated = await service.set_session_persona(
        session.id, name="Sera Vane", description="A wary courier."
    )

    assert updated is not None
    assert updated.user_persona_name == "Sera Vane"
    stored = await session_store.get_by_id(session.id)
    assert stored is not None and stored.user_persona_description == "A wary courier."


@pytest.mark.asyncio
async def test_set_session_persona_replaces_an_existing_one() -> None:
    # The operator path uses `override_persona`; the player-facing `with_persona` guard is
    # untouched and still refuses a second persona.
    session = _session(owner_id=USER_ID).with_persona(name="Sera Vane")
    service, session_store, _, _ = _service(sessions=[session])

    updated = await service.set_session_persona(session.id, name="Sera Vayne")

    assert updated is not None and updated.user_persona_name == "Sera Vayne"
    stored = await session_store.get_by_id(session.id)
    assert stored is not None and stored.user_persona_name == "Sera Vayne"


@pytest.mark.asyncio
async def test_set_session_persona_rejects_a_blank_name() -> None:
    session = _session(owner_id=USER_ID)
    service, _, _, _ = _service(sessions=[session])

    with pytest.raises(ValueError):
        await service.set_session_persona(session.id, name="   ")


@pytest.mark.asyncio
async def test_set_session_persona_returns_none_for_an_unknown_session() -> None:
    service, _, _, _ = _service(sessions=[])

    assert await service.set_session_persona(uuid4(), name="Sera Vane") is None


@pytest.mark.asyncio
async def test_set_session_memory_source_switches_a_layer_off() -> None:
    service, store, _, _ = _service(sessions=[_session(owner_id=USER_ID)])

    updated = await service.set_session_memory_source(
        SESSION_ID, source_id="rolling_summary", enabled=False
    )

    assert updated is not None
    assert updated.memory.is_enabled("rolling_summary") is False
    assert store.sessions[SESSION_ID].memory.is_enabled("rolling_summary") is False


@pytest.mark.asyncio
async def test_set_session_memory_source_returns_none_for_an_unknown_session() -> None:
    service, _, _, _ = _service()

    assert (
        await service.set_session_memory_source(
            SESSION_ID, source_id="rolling_summary", enabled=True
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_session_summary_returns_what_layer_01_stored() -> None:
    stored = SessionSummary.create(
        session_id=SESSION_ID,
        summary="They crossed the river.",
        covers_through_turn=7,
        tokens=9,
        model_name="test-model",
    )
    session_store = FakeScenarioSessionStore([_session(owner_id=USER_ID)])
    service = AdminService(
        user_identity_store=FakeUserIdentityStore([]),
        scenario_session_store=session_store,
        conversation_store=FakeConversationStore(),
        generation_trace_store=FakeGenerationTraceStore(),
        scenario_definition_store=FakeScenarioDefinitionStore(None),
        session_summary_store=FakeSessionSummaryStore(stored),
    )

    assert await service.get_session_summary(SESSION_ID) == stored
