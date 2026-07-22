from pathlib import Path
from uuid import UUID

import pytest

from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.infrastructure.storage.json_scenario_session_store import (
    JsonScenarioSessionStore,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000010")
GROUP_ID = UUID("00000000-0000-0000-0000-000000000020")


@pytest.mark.asyncio
async def test_save_and_load_session(tmp_path: Path) -> None:
    store = JsonScenarioSessionStore(base_path=tmp_path)
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1",
        user_id=USER_ID,
        active_participants={"protagonist": "c1"},
        world_state={"location": "castle"},
        story_progress={"beat": "start"},
        metadata={"difficulty": "hard"},
    )

    await store.save(session)
    loaded = await store.get_by_id(session.id)

    assert loaded is not None
    assert loaded.id == session.id
    assert loaded.scenario_definition_id == "scenario_1"
    assert loaded.owner_kind == "user"
    assert loaded.owner_id == USER_ID
    assert loaded.active_participants == {"protagonist": "c1"}
    assert loaded.world_state == {"location": "castle"}
    assert loaded.story_progress == {"beat": "start"}
    assert loaded.metadata == {"difficulty": "hard"}


@pytest.mark.asyncio
async def test_created_at_survives_round_trip(tmp_path: Path) -> None:
    store = JsonScenarioSessionStore(base_path=tmp_path)
    session = ScenarioSession.create_for_group(
        scenario_definition_id="scenario_1",
        group_id=GROUP_ID,
    )

    await store.save(session)
    loaded = await store.get_by_id(session.id)

    assert loaded is not None
    assert loaded.created_at == session.created_at


@pytest.mark.asyncio
async def test_get_missing_session_returns_none(tmp_path: Path) -> None:
    store = JsonScenarioSessionStore(base_path=tmp_path)

    assert await store.get_by_id(UUID("11111111-1111-1111-1111-111111111111")) is None


@pytest.mark.asyncio
async def test_find_by_owner(tmp_path: Path) -> None:
    store = JsonScenarioSessionStore(base_path=tmp_path)
    session_a = ScenarioSession.create_for_user(
        scenario_definition_id="s1", user_id=USER_ID
    )
    session_b = ScenarioSession.create_for_user(
        scenario_definition_id="s2", user_id=USER_ID
    )
    session_group = ScenarioSession.create_for_group(
        scenario_definition_id="s3", group_id=GROUP_ID
    )
    await store.save(session_a)
    await store.save(session_b)
    await store.save(session_group)

    owned = await store.find_by_owner("user", USER_ID)

    assert {s.id for s in owned} == {session_a.id, session_b.id}


@pytest.mark.asyncio
async def test_delete_session(tmp_path: Path) -> None:
    store = JsonScenarioSessionStore(base_path=tmp_path)
    session = ScenarioSession.create_for_user(
        scenario_definition_id="s1", user_id=USER_ID
    )
    await store.save(session)

    await store.delete(session.id)

    assert await store.get_by_id(session.id) is None
