from uuid import UUID

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

    returned = await store.save(session)
    assert returned == session

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
    assert reloaded.directives.director_instruction == "Raise the stakes."
    # Everything else is untouched by a directive write.
    assert reloaded.metadata == {"difficulty": "hard"}
    assert reloaded.world_state == {"location": "vault"}

    await store.save(reloaded.with_directives(reloaded.directives.without_director_instruction()))
    consumed = await store.get_by_id(session.id)
    assert consumed is not None
    assert consumed.directives.director_instruction == ""
    assert consumed.directives.rules == (first_rule,)

    group_session = ScenarioSession.create_for_group(
        scenario_definition_id="def-2", group_id=GROUP_ID
    )
    assert group_session.directives == SessionDirectives()
    await store.save(group_session)
    assert await store.get_active_for_owner(owner_kind="group", owner_id=GROUP_ID) is None

    await store.delete(session.id)
    assert await store.get_by_id(session.id) is None
