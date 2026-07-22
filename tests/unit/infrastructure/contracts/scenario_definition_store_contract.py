from dataclasses import replace
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.role_profile import RoleProfile
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph
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
        role_profiles={
            "protagonist": RoleProfile(
                id="protagonist",
                name="Protagonist",
                description="The hero",
                objectives=("open the vault",),
                constraints=("stay in character",),
                metadata={"importance": "high"},
            )
        },
        characters={
            "protagonist": Character(
                id="aria",
                owner_id=OWNER_ID,
                visibility=CharacterVisibility.PRIVATE,
                name="Aria",
                description="A cunning thief",
                personality="Bold",
                greeting="Let's begin.",
                metadata={"age": "27"},
            )
        },
        rules=["no meta commentary", "be concise"],
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

    updated = replace(scenario, name="The Sealed Vault (Redux)")
    await store.save(updated)
    reloaded = await store.get_by_id(scenario.id)
    assert reloaded is not None
    assert reloaded.name == "The Sealed Vault (Redux)"
    # Unchanged nested structures survive the update.
    assert reloaded.characters == scenario.characters
    assert reloaded.story_graph == scenario.story_graph

    await store.delete(scenario.id)
    assert await store.get_by_id(scenario.id) is None


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
