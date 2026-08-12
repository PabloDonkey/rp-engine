from dataclasses import replace
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph
from rp_engine.core.scenario.visibility import ScenarioVisibility
from rp_engine.core.world.world import World

OWNER_ID = UUID("00000000-0000-0000-0000-000000000010")
OTHER_OWNER_ID = UUID("00000000-0000-0000-0000-000000000011")


def _rich_scenario(scenario_id: str = "scenario-1") -> ScenarioDefinition:
    return ScenarioDefinition(
        id=scenario_id,
        owner_id=OWNER_ID,
        name="The Sealed Vault",
        description="A heist scenario",
        world=World(
            id="w1",
            name="Eldoria",
            description="A high fantasy realm",
            rules=("magic exists", "dragons are real"),
            metadata={"tone": "grim"},
        ),
        characters={
            "protagonist": Character(
                id="aria",
                name="Aria",
                description="A cunning thief",
                personality="Bold",
                greeting="Let's begin.",
                metadata={"age": "27"},
            )
        },
        rules=["no meta commentary", "be concise"],
        visibility=ScenarioVisibility.RESTRICTED,
        allowed_group_chat_ids=("-100123",),
        story_graph=StoryGraph(
            beats={
                "start": StoryBeat(
                    id="start",
                    description="The approach",
                    transitions={"advance": "vault"},
                    metadata={"scene": "1"},
                ),
                "vault": StoryBeat(id="vault", description="The vault door"),
            },
            entry_beat_id="start",
            metadata={"acts": "2"},
        ),
        initial_context="The moon is high.",
        metadata={"genre": "heist"},
    )


async def assert_scenario_definition_store_contract(store: ScenarioDefinitionStore) -> None:
    scenario = _rich_scenario()

    assert await store.get_by_id(scenario.id) is None

    await store.save(scenario)

    loaded = await store.get_by_id(scenario.id)
    assert loaded == scenario

    owned = await store.find_by_owner(OWNER_ID)
    assert [item.id for item in owned] == [scenario.id]
    assert await store.find_by_owner(OTHER_OWNER_ID) == []

    # list_all() is owner-agnostic — scenarios are one shared library, not per-owner-scoped
    # (visibility, not ownership, controls listing/`/play` access; see ADR-024).
    other_owner_scenario = ScenarioDefinition(
        id="scenario-other-owner", owner_id=OTHER_OWNER_ID, name="Someone Else's", description=""
    )
    await store.save(other_owner_scenario)
    all_ids = {item.id for item in await store.list_all()}
    assert {scenario.id, other_owner_scenario.id} <= all_ids
    await store.delete(other_owner_scenario.id)

    updated = replace(scenario, name="The Sealed Vault (Redux)")
    await store.save(updated)
    reloaded = await store.get_by_id(scenario.id)
    assert reloaded is not None
    assert reloaded.name == "The Sealed Vault (Redux)"
    # Unchanged nested structures survive the update.
    assert reloaded.characters == scenario.characters
    assert reloaded.story_graph == scenario.story_graph

    # `delete` retires rather than erases, so the row is still there — retirement has
    # its own contract below.
    await store.delete(scenario.id)
    assert scenario.id not in {item.id for item in await store.list_all()}


async def assert_scenario_retirement_contract(store: ScenarioDefinitionStore) -> None:
    """The four properties retirement rests on (S030).

    The load-bearing one is the third: the boot import saves every catalog file at every
    start, so a `save()` that touched `deleted_at` would un-retire a curated scenario at
    the next restart.
    """
    scenario = ScenarioDefinition(
        id="retire-me", owner_id=OWNER_ID, name="Retire Me", description=""
    )
    await store.save(scenario)
    assert scenario.id in {item.id for item in await store.list_all()}

    await store.delete(scenario.id)

    # 1. Retiring takes it out of the listing, unless the caller asks for it.
    assert scenario.id not in {item.id for item in await store.list_all()}
    assert scenario.id in {item.id for item in await store.list_all(include_inactive=True)}

    # 2. It still resolves by id, so running stories keep playing and export still works.
    retired = await store.get_by_id(scenario.id)
    assert retired is not None
    assert retired.is_active is False
    assert retired.deleted_at is not None

    # 3. Saving does not resurrect it, and does not disturb the stamp.
    await store.save(replace(scenario, name="Retire Me (edited)"))
    still_retired = await store.get_by_id(scenario.id)
    assert still_retired is not None
    assert still_retired.name == "Retire Me (edited)"
    assert still_retired.is_active is False
    assert still_retired.deleted_at == retired.deleted_at

    # Retiring twice keeps the first stamp: when it was retired stays true.
    await store.delete(scenario.id)
    twice = await store.get_by_id(scenario.id)
    assert twice is not None
    assert twice.deleted_at == retired.deleted_at

    # 4. Restore brings it back to the listing.
    await store.restore(scenario.id)
    restored = await store.get_by_id(scenario.id)
    assert restored is not None
    assert restored.is_active is True
    assert restored.deleted_at is None
    assert scenario.id in {item.id for item in await store.list_all()}


async def assert_minimal_scenario_round_trip(store: ScenarioDefinitionStore) -> None:
    minimal = ScenarioDefinition(
        id="minimal-1",
        owner_id=OWNER_ID,
        name="Bare",
        description="",
    )
    await store.save(minimal)
    loaded = await store.get_by_id("minimal-1")
    assert loaded == minimal
    assert loaded is not None
    assert loaded.world is None
    assert loaded.story_graph is None
    assert loaded.characters == {}
    await store.delete("minimal-1")
