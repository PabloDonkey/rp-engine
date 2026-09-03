from typing import Protocol

from rp_engine.core.scenario.lore_entry import LoreEntry


class LorebookStore(Protocol):
    """Where layer 02 keeps authored lore, scoped to a `ScenarioDefinition`.

    `find_matching` is the one noted exception to ADR-013's split between storage and
    selection (ADR-026): ranking runs inside the repository, because the alternative is
    loading a whole scenario's lorebook into Python to rank it there. `recall_text` is
    the short window `LorebookSource` builds for one turn, not the whole transcript —
    matching only against a short window is what keeps a fired entry from recurring on
    every later turn, with no extra state to track.

    The rest are plain CRUD for the admin surface. `save` is an upsert, scoped by
    `(scenario_definition_id, id)`.
    """

    async def find_matching(
        self, scenario_definition_id: str, recall_text: str, *, limit: int
    ) -> tuple[LoreEntry, ...]: ...

    async def list_for_scenario(self, scenario_definition_id: str) -> tuple[LoreEntry, ...]: ...

    async def get(self, scenario_definition_id: str, entry_id: str) -> LoreEntry | None: ...

    async def save(self, entry: LoreEntry) -> LoreEntry: ...

    async def delete(self, scenario_definition_id: str, entry_id: str) -> None: ...
