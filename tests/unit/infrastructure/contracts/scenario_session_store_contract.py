from dataclasses import replace
from uuid import UUID

from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import SessionDirectives

USER_ID = UUID("00000000-0000-0000-0000-000000000010")
GROUP_ID = UUID("00000000-0000-0000-0000-000000000020")


async def assert_scenario_session_store_contract(store: ScenarioSessionStore) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="def-1",
        user_id=USER_ID,
        active_participants={"character": "aria"},
        world_state={"location": "vault"},
        story_progress={"beat": "start"},
        metadata={"difficulty": "hard"},
    )

    assert await store.get_by_id(session.id) is None

    # `save()` owns `updated_at`, so the *returned* session — not the argument — is the one
    # that matches storage. Everything else round-trips untouched.
    returned = await store.save(session)
    assert returned == replace(session, updated_at=returned.updated_at)
    assert returned.updated_at >= session.updated_at
    assert returned.created_at == session.created_at
    session = returned

    loaded = await store.get_by_id(session.id)
    assert loaded == session

    owned = await store.find_by_owner("user", USER_ID)
    assert [item.id for item in owned] == [session.id]

    found = await store.find_by_definition(
        owner_kind="user", owner_id=USER_ID, scenario_definition_id="def-1"
    )
    assert found is not None
    assert found.id == session.id
    assert (
        await store.find_by_definition(
            owner_kind="user", owner_id=USER_ID, scenario_definition_id="missing"
        )
        is None
    )

    # Active tracking is per owner.
    assert await store.get_active_for_owner(owner_kind="user", owner_id=USER_ID) is None
    await store.set_active_for_owner(
        owner_kind="user", owner_id=USER_ID, session_id=session.id
    )
    active = await store.get_active_for_owner(owner_kind="user", owner_id=USER_ID)
    assert active is not None
    assert active.id == session.id

    # Directives round-trip, and re-saving an existing session updates them in place.
    directives, first_rule = SessionDirectives().with_language("fr").with_rule("No time skips.")
    directives = directives.with_director_instruction("Raise the stakes.")
    await store.save(session.with_directives(directives))

    reloaded = await store.get_by_id(session.id)
    assert reloaded is not None
    assert reloaded.directives.language == "fr"
    assert reloaded.directives.rules == (first_rule,)
    assert reloaded.directives.director_instructions == ("Raise the stakes.",)
    # Everything else is untouched by a directive write.
    assert reloaded.metadata == {"difficulty": "hard"}
    assert reloaded.world_state == {"location": "vault"}

    await store.save(reloaded.with_directives(reloaded.directives.without_director_instructions()))
    consumed = await store.get_by_id(session.id)
    assert consumed is not None
    assert consumed.directives.director_instructions == ()
    assert consumed.directives.rules == (first_rule,)

    # Memory settings round-trip beside the directives, in the same column, without
    # disturbing them (S022).
    await store.save(consumed.with_memory(MemorySettings(enabled_sources=("rolling_summary",))))
    with_memory = await store.get_by_id(session.id)
    assert with_memory is not None
    assert with_memory.memory.enabled_sources == ("rolling_summary",)
    assert with_memory.directives.rules == (first_rule,)
    consumed = with_memory

    # The persona round-trips, including "no description" staying absent rather than "".
    await store.save(consumed.with_persona(name="Sera Vane", description="A wary courier."))
    with_persona = await store.get_by_id(session.id)
    assert with_persona is not None
    assert with_persona.user_persona_name == "Sera Vane"
    assert with_persona.user_persona_description == "A wary courier."

    nameless = ScenarioSession.create_for_user(
        scenario_definition_id="def-3", user_id=USER_ID
    ).with_persona(name="Kes")
    await store.save(nameless)
    reloaded_nameless = await store.get_by_id(nameless.id)
    assert reloaded_nameless is not None
    assert reloaded_nameless.user_persona_name == "Kes"
    assert reloaded_nameless.user_persona_description is None
    await store.delete(nameless.id)

    group_session = ScenarioSession.create_for_group(
        scenario_definition_id="def-2", group_id=GROUP_ID
    )
    assert group_session.directives == SessionDirectives()
    assert group_session.memory == MemorySettings()
    await store.save(group_session)
    assert await store.get_active_for_owner(owner_kind="group", owner_id=GROUP_ID) is None

    # Soft delete: a superseded session leaves every "which session is live?" lookup, but
    # stays readable by id and available to callers that ask for the full history.
    await store.save(with_persona.mark_deleted())
    superseded = await store.get_by_id(session.id)
    assert superseded is not None
    assert superseded.deleted_at is not None
    assert superseded.user_persona_name == "Sera Vane"
    assert (
        await store.find_by_definition(
            owner_kind="user", owner_id=USER_ID, scenario_definition_id="def-1"
        )
        is None
    )
    assert await store.get_active_for_owner(owner_kind="user", owner_id=USER_ID) is None
    assert await store.find_by_owner("user", USER_ID) == []
    all_owned = await store.find_by_owner("user", USER_ID, include_deleted=True)
    assert [item.id for item in all_owned] == [session.id]

    await store.delete(session.id)
    assert await store.get_by_id(session.id) is None


async def assert_live_session_counts_contract(store: ScenarioSessionStore) -> None:
    """One grouped count for the whole catalog (S030).

    The admin scenario list shows this number on every row, so it must come from one query,
    and it must count live sessions only — a superseded story is not somebody playing.
    """
    # Scoped to two ids of its own, so this contract can run after another that leaves
    # sessions behind.
    async def counts() -> dict[str, int]:
        every = await store.count_live_by_definition()
        return {key: value for key, value in every.items() if key in {"count-a", "count-b"}}

    assert await counts() == {}

    first = ScenarioSession.create_for_user(scenario_definition_id="count-a", user_id=USER_ID)
    second = ScenarioSession.create_for_group(scenario_definition_id="count-a", group_id=GROUP_ID)
    third = ScenarioSession.create_for_group(scenario_definition_id="count-b", group_id=GROUP_ID)
    for item in (first, second, third):
        await store.save(item)

    assert await counts() == {"count-a": 2, "count-b": 1}

    # Superseding a story takes it out of the count; the definition it ran stays, because
    # another live session still points at it.
    await store.save(first.mark_deleted())
    assert await counts() == {"count-a": 1, "count-b": 1}

    # The last live session leaving drops the definition from the map entirely.
    await store.save(third.mark_deleted())
    assert await counts() == {"count-a": 1}

    for item in (first, second, third):
        await store.delete(item.id)
