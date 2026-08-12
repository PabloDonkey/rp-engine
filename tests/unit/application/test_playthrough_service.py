from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from rp_engine.application.services.playthrough_service import PlaythroughService
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import SessionDirectives
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID

USER_ID = UUID("00000000-0000-0000-0000-000000000042")
GROUP_ID = UUID("00000000-0000-0000-0000-000000000099")


def _scenario(scenario_id: str, *, name: str, opening: str) -> ScenarioDefinition:
    return ScenarioDefinition(
        id=scenario_id,
        owner_id=SYSTEM_OWNER_ID,
        name=name,
        description=f"{name} description",
        initial_context=opening,
    )


class FakeScenarioDefinitionStore:
    def __init__(self) -> None:
        self.items: dict[str, ScenarioDefinition] = {}

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        return self.items.get(scenario_id)

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        return [s for s in self.items.values() if s.owner_id == owner_id]

    async def list_all(self, *, include_inactive: bool = False) -> list[ScenarioDefinition]:
        return [s for s in self.items.values() if include_inactive or s.is_active]

    async def save(self, scenario: ScenarioDefinition) -> None:
        # Mirrors the real store: `save` never writes `deleted_at`.
        stored = self.items.get(scenario.id)
        deleted_at = stored.deleted_at if stored is not None else None
        self.items[scenario.id] = replace(scenario, deleted_at=deleted_at)

    async def delete(self, scenario_id: str) -> None:
        stored = self.items.get(scenario_id)
        if stored is not None and stored.is_active:
            self.items[scenario_id] = replace(stored, deleted_at=datetime.now(UTC))

    async def restore(self, scenario_id: str) -> None:
        stored = self.items.get(scenario_id)
        if stored is not None:
            self.items[scenario_id] = replace(stored, deleted_at=None)


class FakeScenarioSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[UUID, ScenarioSession] = {}
        self.active: dict[tuple[str, UUID], UUID] = {}

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
        # Mirrors the real store: superseded sessions are invisible here, newest first.
        matches = sorted(
            (
                s
                for s in self.sessions.values()
                if s.owner_kind == owner_kind
                and s.owner_id == owner_id
                and s.scenario_definition_id == scenario_definition_id
                and not s.is_deleted
            ),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return matches[0] if matches else None

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
        self, *, owner_kind: str, owner_id: UUID, session_id: UUID
    ) -> None:
        self.active[(owner_kind, owner_id)] = session_id

    async def get_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID
    ) -> ScenarioSession | None:
        session_id = self.active.get((owner_kind, owner_id))
        session = self.sessions.get(session_id) if session_id else None
        return None if session is None or session.is_deleted else session


class FakeConversationStore:
    def __init__(self) -> None:
        self.messages: dict[str, list[ConversationMessage]] = {}

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        self.messages.setdefault(memory_key.value, []).append(message)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self.messages.get(memory_key.value, []))

    async def clear(self, memory_key: MemoryKey) -> None:
        self.messages.pop(memory_key.value, None)


def _service(
    *,
    scenarios: list[ScenarioDefinition],
) -> tuple[PlaythroughService, FakeScenarioSessionStore, FakeConversationStore]:
    definition_store = FakeScenarioDefinitionStore()
    definition_store.items = {scenario.id: scenario for scenario in scenarios}
    session_store = FakeScenarioSessionStore()
    conversation_store = FakeConversationStore()
    service = PlaythroughService(
        scenario_definition_store=definition_store,
        scenario_session_store=session_store,
        conversation_store=conversation_store,
    )
    return service, session_store, conversation_store


def _memory_key(session_id: UUID) -> MemoryKey:
    return ConversationIdentity.for_session(str(session_id)).to_memory_key()


@pytest.mark.asyncio
async def test_list_scenarios_sorted_by_name() -> None:
    service, _, _ = _service(
        scenarios=[
            _scenario("b", name="Zephyr", opening="z"),
            _scenario("a", name="Aurora", opening="a"),
        ]
    )
    assert [s.name for s in await service.list_scenarios()] == ["Aurora", "Zephyr"]


@pytest.mark.asyncio
async def test_start_creates_active_session_and_seeds_opening() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, conversation_store = _service(scenarios=[scenario])

    result = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    assert result is not None
    assert result.opening == "You face the door."
    assert result.scenario.id == "vault"

    active = await session_store.get_active_for_owner(owner_kind="user", owner_id=USER_ID)
    assert active is not None
    assert active.id == result.session.id
    assert active.scenario_definition_id == "vault"

    history = conversation_store.messages[_memory_key(result.session.id).value]
    assert history == [
        ConversationMessage(role=ConversationRole.CHARACTER, content="You face the door.")
    ]


@pytest.mark.asyncio
async def test_start_same_scenario_twice_resumes_existing_session() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, conversation_store = _service(scenarios=[scenario])

    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    assert first.resumed is False
    await conversation_store.save_message(
        _memory_key(first.session.id),
        ConversationMessage(role=ConversationRole.USER, content="I open it."),
    )
    await conversation_store.save_message(
        _memory_key(first.session.id),
        ConversationMessage(role=ConversationRole.CHARACTER, content="The door creaks open."),
    )

    second = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    assert second is not None
    assert second.session.id == first.session.id
    assert second.resumed is True
    assert second.opening == "The door creaks open."
    # History was preserved, not wiped, by resuming instead of restarting.
    history = conversation_store.messages[_memory_key(first.session.id).value]
    assert len(history) == 3

    active = await session_store.get_active_for_owner(owner_kind="user", owner_id=USER_ID)
    assert active is not None and active.id == first.session.id


@pytest.mark.asyncio
async def test_start_unknown_scenario_returns_none() -> None:
    service, _, _ = _service(scenarios=[])
    assert await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="nope") is None


@pytest.mark.asyncio
async def test_restart_supersedes_the_old_session_and_starts_fresh() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, conversation_store = _service(scenarios=[scenario])

    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    # Simulate some play.
    await conversation_store.save_message(
        _memory_key(first.session.id),
        ConversationMessage(role=ConversationRole.USER, content="I open it."),
    )

    second = await service.restart(owner_kind="user", owner_id=USER_ID)

    assert second is not None
    assert second.session.id != first.session.id
    # The old session is superseded rather than orphaned or purged: it keeps its whole
    # transcript for debugging, but no longer counts as the player's session.
    superseded = await session_store.get_by_id(first.session.id)
    assert superseded is not None and superseded.is_deleted
    assert len(conversation_store.messages[_memory_key(first.session.id).value]) == 2
    # New playthrough seeded with the opening only.
    new_history = conversation_store.messages[_memory_key(second.session.id).value]
    assert new_history == [
        ConversationMessage(role=ConversationRole.CHARACTER, content="You face the door.")
    ]
    active = await session_store.get_active_for_owner(owner_kind="user", owner_id=USER_ID)
    assert active is not None and active.id == second.session.id


@pytest.mark.asyncio
async def test_replaying_a_scenario_after_a_restart_resumes_the_new_session() -> None:
    """The session-resurrection regression: before superseded sessions were filtered out,
    `find_by_definition` could hand back a *pre*-restart session and its old transcript."""
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, _, conversation_store = _service(scenarios=[scenario])

    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    await conversation_store.save_message(
        _memory_key(first.session.id),
        ConversationMessage(role=ConversationRole.CHARACTER, content="The old story."),
    )
    second = await service.restart(owner_kind="user", owner_id=USER_ID)
    assert second is not None

    replayed = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    assert replayed is not None
    assert replayed.resumed is True
    assert replayed.session.id == second.session.id
    assert replayed.opening == "You face the door."


@pytest.mark.asyncio
async def test_restart_without_active_returns_none() -> None:
    service, _, _ = _service(scenarios=[])
    assert await service.restart(owner_kind="user", owner_id=USER_ID) is None


@pytest.mark.asyncio
async def test_get_active_and_resume_text() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, _, conversation_store = _service(scenarios=[scenario])
    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert started is not None

    await conversation_store.save_message(
        _memory_key(started.session.id),
        ConversationMessage(role=ConversationRole.USER, content="I step inside."),
    )
    await conversation_store.save_message(
        _memory_key(started.session.id),
        ConversationMessage(role=ConversationRole.CHARACTER, content="The hall is silent."),
    )

    active = await service.get_active(owner_kind="user", owner_id=USER_ID)
    assert active is not None
    resume = await service.resume_text(session=active)
    assert resume == "The hall is silent."


@pytest.mark.asyncio
async def test_group_playthrough_is_independent() -> None:
    scenario = _scenario("vault", name="Vault", opening="Opening.")
    service, _, _ = _service(scenarios=[scenario])

    await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    await service.start(owner_kind="group", owner_id=GROUP_ID, scenario_id="vault")

    user_active = await service.get_active(owner_kind="user", owner_id=USER_ID)
    group_active = await service.get_active(owner_kind="group", owner_id=GROUP_ID)
    assert user_active is not None and group_active is not None
    assert user_active.id != group_active.id
    assert group_active.owner_kind == "group"


@pytest.mark.asyncio
async def test_restart_carries_persistent_directives_but_drops_the_director_note() -> None:
    """Restarting the story is not a request to re-configure it, so language and rules
    follow the player into the fresh session; the pending one-turn director note was
    aimed at a reply that will now never happen."""
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, _ = _service(scenarios=[scenario])

    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    directives, _ = SessionDirectives().with_language("fr").with_rule("No time skips.")
    await session_store.save(
        first.session.with_directives(directives.with_director_instruction("Raise the stakes."))
    )

    second = await service.restart(owner_kind="user", owner_id=USER_ID)

    assert second is not None
    assert second.session.directives.language == "fr"
    assert [rule.text for rule in second.session.directives.rules] == ["No time skips."]
    assert second.session.directives.director_instructions == ()


@pytest.mark.asyncio
async def test_new_playthrough_starts_with_default_directives() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, _, _ = _service(scenarios=[scenario])

    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    assert started is not None
    assert started.session.directives == SessionDirectives()


# --------------------------------------------------------------------------- #
# Reset tiers (ADR-025) and persona capture (S015)
# --------------------------------------------------------------------------- #


async def _configured_playthrough(
    service: PlaythroughService, session_store: FakeScenarioSessionStore
) -> None:
    """Give the active session everything a player can own: persona, language, rules and a
    pending director note."""
    active = await service.get_active(owner_kind="user", owner_id=USER_ID)
    assert active is not None
    directives, _ = SessionDirectives().with_language("fr").with_rule("No time skips.")
    await session_store.save(
        active.with_persona(name="Sera Vane", description="A wary courier.").with_directives(
            directives.with_director_instruction("Raise the stakes.")
        )
    )


@pytest.mark.asyncio
async def test_restart_carries_the_persona_forward() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, _ = _service(scenarios=[scenario])
    await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    await _configured_playthrough(service, session_store)

    restarted = await service.restart(owner_kind="user", owner_id=USER_ID)

    assert restarted is not None
    assert restarted.session.user_persona_name == "Sera Vane"
    assert restarted.session.user_persona_description == "A wary courier."


@pytest.mark.asyncio
async def test_clear_resets_every_player_owned_setting() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, _ = _service(scenarios=[scenario])
    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    await _configured_playthrough(service, session_store)

    cleared = await service.clear(owner_kind="user", owner_id=USER_ID)

    assert cleared is not None
    assert cleared.session.id != first.session.id
    assert cleared.session.has_persona is False
    assert cleared.session.directives == SessionDirectives()


@pytest.mark.asyncio
async def test_clear_supersedes_the_old_session_like_restart_does() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, _ = _service(scenarios=[scenario])
    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None

    await service.clear(owner_kind="user", owner_id=USER_ID)

    superseded = await session_store.get_by_id(first.session.id)
    assert superseded is not None and superseded.is_deleted
    # ...and it is not resurrectable by replaying the same scenario.
    replayed = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert replayed is not None and replayed.session.id != first.session.id


@pytest.mark.asyncio
async def test_clear_without_active_returns_none() -> None:
    service, _, _ = _service(scenarios=[])
    assert await service.clear(owner_kind="user", owner_id=USER_ID) is None


@pytest.mark.asyncio
async def test_set_persona_attaches_the_persona_and_returns_the_intro() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, session_store, _ = _service(scenarios=[scenario])
    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert started is not None

    result = await service.set_persona(
        session_id=started.session.id, name="Sera Vane", description="A wary courier."
    )

    assert result is not None
    assert result.opening == "You face the door."
    stored = await session_store.get_by_id(started.session.id)
    assert stored is not None
    assert stored.user_persona_name == "Sera Vane"
    assert stored.user_persona_description == "A wary courier."


@pytest.mark.asyncio
async def test_set_persona_refuses_a_session_that_already_has_one() -> None:
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, _, _ = _service(scenarios=[scenario])
    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert started is not None
    await service.set_persona(session_id=started.session.id, name="Sera Vane")

    assert await service.set_persona(session_id=started.session.id, name="Someone Else") is None


@pytest.mark.asyncio
async def test_set_persona_refuses_a_superseded_session() -> None:
    """A reply that arrives after the player restarted must not land on the dead session."""
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    service, _, _ = _service(scenarios=[scenario])
    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert started is not None
    await service.clear(owner_kind="user", owner_id=USER_ID)

    assert await service.set_persona(session_id=started.session.id, name="Sera Vane") is None


# --- retired scenarios (S030 step 2) ----------------------------------------------------


@pytest.mark.asyncio
async def test_play_refuses_a_retired_scenario() -> None:
    retired = replace(
        _scenario("vault", name="Vault", opening="You face the door."),
        deleted_at=datetime.now(UTC),
    )
    service, session_store, _ = _service(scenarios=[retired])

    result = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    # Same answer as an unknown id: retirement must not leak through a distinct reply.
    assert result is None
    assert await session_store.get_active_for_owner(owner_kind="user", owner_id=USER_ID) is None


@pytest.mark.asyncio
async def test_a_retired_scenario_leaves_the_catalog_listing() -> None:
    live = _scenario("live", name="Aurora", opening="a")
    retired = replace(_scenario("gone", name="Zephyr", opening="z"), deleted_at=datetime.now(UTC))
    service, _, _ = _service(scenarios=[live, retired])

    assert [s.id for s in await service.list_scenarios()] == ["live"]


@pytest.mark.asyncio
async def test_a_story_already_running_survives_its_scenario_being_retired() -> None:
    """Retirement closes the front door. It does not evict the people already inside."""
    scenario = _scenario("vault", name="Vault", opening="You face the door.")
    definition_store = FakeScenarioDefinitionStore()
    definition_store.items = {scenario.id: scenario}
    session_store = FakeScenarioSessionStore()
    service = PlaythroughService(
        scenario_definition_store=definition_store,
        scenario_session_store=session_store,
        conversation_store=FakeConversationStore(),
    )
    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert started is not None

    await definition_store.delete("vault")
    assert await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault") is None

    active = await session_store.get_active_for_owner(owner_kind="user", owner_id=USER_ID)
    assert active is not None
    assert active.id == started.session.id
    # `/restart` keeps working for a story that is already under way.
    assert await service.restart(owner_kind="user", owner_id=USER_ID) is not None
