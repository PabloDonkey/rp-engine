"""Which memory layers a session runs, and how much of the budget each one may take.

Shaped like `SessionDirectives`: a frozen value object on `ScenarioSession`, stored in the
session's existing payload, every change returning a new instance. Under ADR-025 it is
player-owned state, so `/restart` carries it forward and `/clear` resets it.

Layer 00 is absent from this type on purpose. It is the conversation itself, so "recent
window off" must not be expressible — see `ToggleableMemorySystemId`.
"""

from collections.abc import Collection
from dataclasses import dataclass, replace

from rp_engine.core.memory.fragment import MemorySystemId, ToggleableMemorySystemId

# The layers that are on when a session says nothing. Layer 01 is on by default because it
# is the only thing that speaks for the story once the window has moved past it, and a
# session that has to be told to remember is a session that already forgot.
DEFAULT_ENABLED_SOURCES: tuple[ToggleableMemorySystemId, ...] = ("rolling_summary",)

# The share of the memory budget layer 01 may spend. It is a share rather than a token
# count for the same reason the whole budget is (ADR-026): a hand-set number goes silently
# wrong the moment a model with a different window is loaded. A quarter is enough for the
# 50-to-150-word recap the summarizer is asked for, at any window size worth playing on.
DEFAULT_SOURCE_BUDGET_SHARES: tuple[tuple[ToggleableMemorySystemId, float], ...] = (
    ("rolling_summary", 0.25),
)


@dataclass(frozen=True, slots=True)
class MemorySourceBudget:
    """How much of the memory budget one layer may take, as a share of it.

    A layer with no entry here is offered what the other layers' shares leave. That is what
    layer 00 gets, and it is the whole budget for as long as no other layer claims a share.
    """

    source: ToggleableMemorySystemId
    share: float

    def __post_init__(self) -> None:
        if not 0.0 < self.share <= 1.0:
            raise ValueError("A memory source budget share must be greater than 0 and at most 1.")


DEFAULT_SOURCE_BUDGETS: tuple[MemorySourceBudget, ...] = tuple(
    MemorySourceBudget(source=source, share=share) for source, share in DEFAULT_SOURCE_BUDGET_SHARES
)


@dataclass(frozen=True, slots=True)
class MemorySettings:
    enabled_sources: tuple[ToggleableMemorySystemId, ...] = DEFAULT_ENABLED_SOURCES
    source_budgets: tuple[MemorySourceBudget, ...] = DEFAULT_SOURCE_BUDGETS

    def is_enabled(self, source_id: MemorySystemId) -> bool:
        """Layer 00 is always on; the rest answer from the enabled set."""
        if source_id == "recent_window":
            return True
        return source_id in self.enabled_sources

    def budget_for(
        self,
        source_id: MemorySystemId,
        available: int,
        *,
        among: Collection[MemorySystemId] | None = None,
    ) -> int:
        """The tokens this layer may spend out of `available`.

        A layer with a share gets exactly that share. A layer with no share gets what the
        shares of the *enabled* layers leave — which is what layer 00 gets, and it is why
        the shares never have to add up to one.

        `among` is the set of layers this build actually runs, which the pipeline knows and
        the settings do not. A layer a session enabled but this build does not have holds
        back nothing; without it, a session carrying a switched-on layer from a newer build
        would quietly shrink the window of an older one.

        The subtraction is what makes a share mean anything. The recent window would
        otherwise fill the whole budget with turns, and every lower-priority fragment would
        then be dropped by the cut for want of room, so a layer's share would buy it
        nothing. The cost is that an unused share is wasted for that turn: a recap shorter
        than its allowance leaves the difference unspent rather than handing it back.
        """
        for budget in self.source_budgets:
            if budget.source == source_id:
                return max(0, min(available, int(available * budget.share)))
        reserved = sum(
            int(available * budget.share)
            for budget in self.source_budgets
            if budget.source != source_id
            and self.is_enabled(budget.source)
            and (among is None or budget.source in among)
        )
        return max(0, available - reserved)

    def with_source_enabled(self, source_id: ToggleableMemorySystemId) -> "MemorySettings":
        if source_id in self.enabled_sources:
            return self
        return replace(self, enabled_sources=(*self.enabled_sources, source_id))

    def with_source_disabled(self, source_id: ToggleableMemorySystemId) -> "MemorySettings":
        remaining = tuple(enabled for enabled in self.enabled_sources if enabled != source_id)
        if len(remaining) == len(self.enabled_sources):
            return self
        return replace(self, enabled_sources=remaining)

    def with_source_budget(
        self, source_id: ToggleableMemorySystemId, share: float
    ) -> "MemorySettings":
        """Set one layer's share. Raises ValueError when the share is outside (0, 1]."""
        updated = MemorySourceBudget(source=source_id, share=share)
        others = tuple(budget for budget in self.source_budgets if budget.source != source_id)
        return replace(self, source_budgets=(*others, updated))
