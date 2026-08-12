from uuid import UUID, uuid4

import pytest

from rp_engine.application.services.session_directive_service import SessionDirectiveService
from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind
from rp_engine.core.scenario.session_directives import SessionDirectives

USER_ID = UUID("00000000-0000-0000-0000-000000000042")


class InMemoryScenarioSessionStore(ScenarioSessionStore):
    def __init__(self) -> None:
        self.sessions: dict[UUID, ScenarioSession] = {}

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        return self.sessions.get(session_id)

    async def find_by_owner(
        self, owner_kind: str, owner_id: UUID, *, include_deleted: bool = False
    ) -> list[ScenarioSession]:
        return [
            session
            for session in self.sessions.values()
            if session.owner_kind == owner_kind
            and session.owner_id == owner_id
            and (include_deleted or not session.is_deleted)
        ]

    async def find_by_definition(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        for session in self.sessions.values():
            if (
                session.owner_kind == owner_kind
                and session.owner_id == owner_id
                and session.scenario_definition_id == scenario_definition_id
            ):
                return session
        return None

    async def count_live_by_definition(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for stored in self.sessions.values():
            if not stored.is_deleted:
                key = stored.scenario_definition_id
                counts[key] = counts.get(key, 0) + 1
        return counts

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        self.sessions[session.id] = session
        return session

    async def delete(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        return None

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        return None


@pytest.fixture
def store() -> InMemoryScenarioSessionStore:
    return InMemoryScenarioSessionStore()


@pytest.fixture
def service(store: InMemoryScenarioSessionStore) -> SessionDirectiveService:
    return SessionDirectiveService(scenario_session_store=store)


def _session() -> ScenarioSession:
    return ScenarioSession.create_for_user(
        scenario_definition_id="vault",
        user_id=USER_ID,
    )


@pytest.mark.asyncio
async def test_set_language_persists_the_session(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session()

    directives = await service.set_language(session=session, language="FR")

    assert directives.language == "fr"
    assert store.sessions[session.id].directives.language == "fr"


@pytest.mark.asyncio
async def test_set_language_rejects_unsupported_code(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session()

    with pytest.raises(ValueError):
        await service.set_language(session=session, language="klingon")

    assert store.sessions == {}


@pytest.mark.asyncio
async def test_add_and_remove_rules(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session()

    first = await service.add_rule(session=session, text="Keep replies short.")
    # Adding builds on the *stored* session, so the caller must re-read between writes.
    second = await service.add_rule(session=store.sessions[session.id], text="No time skips.")

    assert (first.id, second.id) == ("1", "2")
    assert [rule.text for rule in store.sessions[session.id].directives.rules] == [
        "Keep replies short.",
        "No time skips.",
    ]

    removed = await service.remove_rule(session=store.sessions[session.id], rule_id="1")
    assert removed is True
    assert [rule.id for rule in store.sessions[session.id].directives.rules] == ["2"]


@pytest.mark.asyncio
async def test_remove_unknown_rule_reports_false_and_writes_nothing(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session()
    await service.add_rule(session=session, text="Keep replies short.")
    stored = store.sessions[session.id]

    removed = await service.remove_rule(session=stored, rule_id="99")

    assert removed is False
    assert store.sessions[session.id] == stored


@pytest.mark.asyncio
async def test_director_instruction_round_trip(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session()

    await service.add_director_instruction(session=session, instruction="Raise the stakes.")
    assert store.sessions[session.id].directives.director_instructions == ("Raise the stakes.",)

    await service.clear_director_instructions(session=store.sessions[session.id])
    assert store.sessions[session.id].directives.director_instructions == ()


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_session(service: SessionDirectiveService) -> None:
    assert await service.get(session_id=uuid4()) is None


@pytest.mark.asyncio
async def test_get_returns_stored_directives(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session().with_directives(SessionDirectives(language="fr"))
    await store.save(session)

    directives = await service.get(session_id=session.id)

    assert directives is not None
    assert directives.language == "fr"


@pytest.mark.asyncio
async def test_writes_do_not_disturb_the_rest_of_the_session(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="vault",
        user_id=USER_ID,
        active_participants={"protagonist": "aria"},
        world_state={"location": "vault"},
        metadata={"difficulty": "hard"},
    )

    await service.set_language(session=session, language="fr")

    stored = store.sessions[session.id]
    assert stored.active_participants == {"protagonist": "aria"}
    assert stored.world_state == {"location": "vault"}
    assert stored.metadata == {"difficulty": "hard"}
    assert stored.created_at == session.created_at


@pytest.mark.asyncio
async def test_switching_a_memory_layer_off_is_persisted(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session()
    await store.save(session)

    updated = await service.set_memory_source(
        session=session, source_id="rolling_summary", enabled=False
    )

    assert updated.is_enabled("rolling_summary") is False
    assert store.sessions[session.id].memory.is_enabled("rolling_summary") is False


@pytest.mark.asyncio
async def test_switching_a_memory_layer_on_is_persisted(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    session = _session().with_memory(MemorySettings(enabled_sources=()))
    await store.save(session)

    await service.set_memory_source(session=session, source_id="rolling_summary", enabled=True)

    assert store.sessions[session.id].memory.is_enabled("rolling_summary") is True


@pytest.mark.asyncio
async def test_a_memory_write_leaves_the_directives_alone(
    service: SessionDirectiveService,
    store: InMemoryScenarioSessionStore,
) -> None:
    # The two live in one JSONB document, so a write to either must carry the other.
    session = _session().with_directives(SessionDirectives(language="fr"))
    await store.save(session)

    await service.set_memory_source(session=session, source_id="rolling_summary", enabled=False)

    assert store.sessions[session.id].directives.language == "fr"
