from pathlib import Path
from uuid import UUID

import pytest

from rp_engine.core.character.character import Character
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph
from rp_engine.core.scenario.visibility import ScenarioVisibility
from rp_engine.core.world.world import World
from rp_engine.infrastructure.storage.json_scenario_definition_store import (
    JsonScenarioDefinitionStore,
)

OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_save_and_load_minimal_scenario(tmp_path: Path) -> None:
    store = JsonScenarioDefinitionStore(base_path=tmp_path)
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=OWNER_ID,
        name="Minimal",
        description="A minimal scenario",
    )

    await store.save(scenario)
    loaded = await store.get_by_id("scenario_1")

    assert loaded is not None
    assert loaded.id == "scenario_1"
    assert loaded.owner_id == OWNER_ID
    assert loaded.world is None
    assert loaded.characters == {}
    assert loaded.story_graph is None
    assert loaded.visibility is ScenarioVisibility.PUBLIC
    assert loaded.allowed_group_chat_ids == ()


@pytest.mark.asyncio
async def test_full_scenario_round_trip(tmp_path: Path) -> None:
    store = JsonScenarioDefinitionStore(base_path=tmp_path)
    world = World(
        id="w1",
        name="Eldoria",
        description="A high fantasy realm",
        rules=("magic exists", "dragons are real"),
    )
    character = Character(
        id="c1",
        name="Aria",
        description="A brave knight",
        personality="Loyal and bold",
        greeting="Well met, traveler.",
    )
    story_graph = StoryGraph(
        beats={
            "start": StoryBeat(
                id="start",
                description="The journey begins",
                transitions={"advance": "climax"},
            ),
            "climax": StoryBeat(id="climax", description="The final battle"),
        },
        entry_beat_id="start",
        metadata={"acts": "3"},
    )
    scenario = ScenarioDefinition(
        id="scenario_full",
        owner_id=OWNER_ID,
        name="Full Scenario",
        description="Everything populated",
        world=world,
        characters={"protagonist": character},
        rules=["be respectful", "no meta commentary"],
        story_graph=story_graph,
        initial_context="It was the dawn of a new age...",
        visibility=ScenarioVisibility.RESTRICTED,
        allowed_group_chat_ids=("-100999",),
        metadata={"genre": "fantasy"},
    )

    await store.save(scenario)
    loaded = await store.get_by_id("scenario_full")

    assert loaded is not None
    assert loaded.world == world
    assert loaded.rules == ["be respectful", "no meta commentary"]
    assert loaded.initial_context == "It was the dawn of a new age..."
    assert loaded.metadata == {"genre": "fantasy"}

    assert loaded.characters["protagonist"] == character
    assert loaded.visibility is ScenarioVisibility.RESTRICTED
    assert loaded.allowed_group_chat_ids == ("-100999",)

    assert loaded.story_graph is not None
    assert loaded.story_graph.entry_beat_id == "start"
    assert loaded.story_graph.beats["start"].transitions == {"advance": "climax"}
    assert loaded.story_graph.beats["climax"].description == "The final battle"


@pytest.mark.asyncio
async def test_get_missing_scenario_returns_none(tmp_path: Path) -> None:
    store = JsonScenarioDefinitionStore(base_path=tmp_path)

    assert await store.get_by_id("does_not_exist") is None


@pytest.mark.asyncio
async def test_find_by_owner(tmp_path: Path) -> None:
    store = JsonScenarioDefinitionStore(base_path=tmp_path)
    other_owner = UUID("00000000-0000-0000-0000-000000000002")

    await store.save(
        ScenarioDefinition(id="a", owner_id=OWNER_ID, name="A", description="")
    )
    await store.save(
        ScenarioDefinition(id="b", owner_id=OWNER_ID, name="B", description="")
    )
    await store.save(
        ScenarioDefinition(id="c", owner_id=other_owner, name="C", description="")
    )

    owned = await store.find_by_owner(OWNER_ID)

    assert {s.id for s in owned} == {"a", "b"}


@pytest.mark.asyncio
async def test_delete_scenario(tmp_path: Path) -> None:
    store = JsonScenarioDefinitionStore(base_path=tmp_path)
    await store.save(
        ScenarioDefinition(id="temp", owner_id=OWNER_ID, name="Temp", description="")
    )

    await store.delete("temp")

    assert await store.get_by_id("temp") is None
