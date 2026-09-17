from uuid import UUID

from rp_engine.core.ports.lorebook_store import LorebookStore
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.lore_entry import LoreEntry
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition

OWNER_ID = UUID("00000000-0000-0000-0000-000000000040")


async def _new_scenario(definition_store: ScenarioDefinitionStore, scenario_id: str) -> str:
    """`lorebook_entries.scenario_definition_id` is a real foreign key: the row it points
    at has to exist first, unlike `scenario_sessions` (see `session_summary_store_contract`).
    """
    await definition_store.save(
        ScenarioDefinition.create(
            scenario_id=scenario_id,
            owner_id=OWNER_ID,
            name="Contract test scenario",
            description="Exists only to satisfy lorebook_entries' foreign key.",
        )
    )
    return scenario_id


async def assert_lorebook_store_contract(
    store: LorebookStore,
    *,
    definition_store: ScenarioDefinitionStore,
) -> None:
    """CRUD and scoping. `find_matching`'s retrieval behavior is a separate function
    below — it is the one part of this layer worth real Postgres for (ADR-026's noted
    exception puts ranking inside the repository, so a fake store cannot exercise it).
    """
    scenario_id = await _new_scenario(definition_store, "lore-contract-scenario")
    other_scenario_id = await _new_scenario(definition_store, "lore-contract-other-scenario")

    assert await store.get(scenario_id, "missing") is None
    assert await store.list_for_scenario(scenario_id) == ()

    entry = LoreEntry.create(
        entry_id="dragon-hoard",
        scenario_definition_id=scenario_id,
        title="The Dragon's Hoard",
        content="A dragon guards a hoard of gold beneath the mountain.",
        trigger_keys=["dragon"],
    )
    saved = await store.save(entry)
    assert saved == entry
    assert await store.get(scenario_id, "dragon-hoard") == entry

    # save() upserts in place: saving the same id again updates the row, not adds one.
    updated = entry.rewritten(
        title="The Dragon's Hoard",
        content="A dragon guards a hoard of silver beneath the mountain.",
        trigger_keys=["dragon"],
        priority="high",
        related_entry_ids=(),
    )
    await store.save(updated)
    reloaded = await store.get(scenario_id, "dragon-hoard")
    assert reloaded is not None
    assert reloaded.content == "A dragon guards a hoard of silver beneath the mountain."
    assert reloaded.priority == "high"
    assert len(await store.list_for_scenario(scenario_id)) == 1

    # Scoped by (scenario_definition_id, id): invisible under a different scenario.
    assert await store.get(other_scenario_id, "dragon-hoard") is None
    assert await store.list_for_scenario(other_scenario_id) == ()

    # delete() removes only the addressed row.
    await store.delete(scenario_id, "dragon-hoard")
    assert await store.get(scenario_id, "dragon-hoard") is None


async def assert_lorebook_store_matching_contract(
    store: LorebookStore,
    *,
    definition_store: ScenarioDefinitionStore,
) -> None:
    """`find_matching`'s Postgres full-text behavior — a stem match, not a substring check.

    Two facts confirmed by hand against a real database while building this layer
    (`.devloop/archive/S024-2026-09-03-lorebook.md`), asserted here so they cannot regress
    silently:
    - "dragon" and "dragons" share a stem (ADR-026's own worked example) — a trigger fires
      on either spelling.
    - "strong" and "strength" do NOT share a stem in Postgres's English dictionary — a
      trigger written as one will not fire on text that only uses the other. This was a
      real authoring bug the pilot hit, not a hypothetical.
    """
    scenario_id = await _new_scenario(definition_store, "lore-matching-scenario")

    await store.save(
        LoreEntry.create(
            entry_id="dragon-lore",
            scenario_definition_id=scenario_id,
            title="Dragons",
            content="Dragons once ruled these mountains.",
            trigger_keys=["dragon"],
        )
    )
    await store.save(
        LoreEntry.create(
            entry_id="strong-lore",
            scenario_definition_id=scenario_id,
            title="A Strongman's Feat",
            content="He lifted the gate alone.",
            trigger_keys=["strong"],
        )
    )
    await store.save(
        LoreEntry.create(
            entry_id="castle-guard-lore",
            scenario_definition_id=scenario_id,
            title="The Night Watch",
            content="A guard has stood at the castle gate for a hundred years.",
            trigger_keys=["castle guard"],
        )
    )

    # Shared stem: "dragons" in the recall text fires a trigger of "dragon".
    matches = await store.find_matching(scenario_id, "I heard the dragons are back", limit=5)
    assert [m.id for m in matches] == ["dragon-lore"]

    # Unrelated lexemes: "strength" does not fire a trigger of "strong".
    matches = await store.find_matching(scenario_id, "she showed great strength today", limit=5)
    assert matches == ()

    # No shared stem with any entry's triggers: matches nothing.
    matches = await store.find_matching(scenario_id, "the weather today is calm and mild", limit=5)
    assert matches == ()

    # A multi-word trigger phrase is an AND of its words (see `_trigger_query_expr`):
    # both words present anywhere in the recall text fires it.
    matches = await store.find_matching(scenario_id, "the castle guard is asleep", limit=5)
    assert [m.id for m in matches] == ["castle-guard-lore"]

    # Only one of the two words present: the AND fails, so it does not fire.
    matches = await store.find_matching(scenario_id, "the guard is asleep", limit=5)
    assert matches == ()

    # limit is honored.
    limited = await store.find_matching(scenario_id, "dragons and a castle guard", limit=1)
    assert len(limited) == 1
