"""One authored fact about a scenario or its characters (layer 02, ADR-026).

Lore is contextual knowledge, not a personality prompt: it is written to be retrieved
only when the current scene touches it, not carried in every prompt. It is scoped to a
`ScenarioDefinition`, not to a `Character` — matching `Character` being an optional
embedded asset rather than a root entity (`docs/DOMAIN_MODEL.md`).

`trigger_keys` are what a person writes; `LorebookStore.find_matching` derives the actual
Postgres `tsquery` from them at write time (see the store), so this type stays free of
that detail.

`related_entry_ids` stays inert data for now: it is shown to whoever edits lore, but
retrieval never expands through it. Auto-expanding a chain of related entries risks
exactly the "dump the whole biography" failure this layer exists to avoid.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

LoreEntryPriority = Literal["low", "normal", "high"]


@dataclass(frozen=True, slots=True)
class LoreEntry:
    id: str
    scenario_definition_id: str
    title: str
    content: str
    trigger_keys: tuple[str, ...]
    priority: LoreEntryPriority
    related_entry_ids: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        entry_id: str,
        scenario_definition_id: str,
        title: str,
        content: str,
        trigger_keys: tuple[str, ...] | list[str],
        priority: LoreEntryPriority = "normal",
        related_entry_ids: tuple[str, ...] | list[str] = (),
        now: datetime | None = None,
    ) -> "LoreEntry":
        stamp = now or datetime.now(UTC)
        return cls(
            id=entry_id,
            scenario_definition_id=scenario_definition_id,
            title=title,
            content=content,
            trigger_keys=tuple(trigger_keys),
            priority=priority,
            related_entry_ids=tuple(related_entry_ids),
            created_at=stamp,
            updated_at=stamp,
        )

    def rewritten(
        self,
        *,
        title: str,
        content: str,
        trigger_keys: tuple[str, ...] | list[str],
        priority: LoreEntryPriority,
        related_entry_ids: tuple[str, ...] | list[str],
        now: datetime | None = None,
    ) -> "LoreEntry":
        """The next version of this entry, as an operator edits it. `created_at` stays."""
        return replace(
            self,
            title=title,
            content=content,
            trigger_keys=tuple(trigger_keys),
            priority=priority,
            related_entry_ids=tuple(related_entry_ids),
            updated_at=now or datetime.now(UTC),
        )
