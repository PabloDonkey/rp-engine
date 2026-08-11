"""Which memory layers a session runs.

Shaped like `SessionDirectives`: a frozen value object on `ScenarioSession`, stored in the
session's existing payload, every change returning a new instance. Under ADR-025 it is
player-owned state, so `/restart` carries it forward and `/clear` resets it.

Layer 00 is absent from this type on purpose. It is the conversation itself, so "recent
window off" must not be expressible — see `ToggleableMemorySystemId`.
"""

from dataclasses import dataclass, replace

from rp_engine.core.memory.fragment import MemorySystemId, ToggleableMemorySystemId

# The layers that are on when a session says nothing. Empty today: S022 ships layer 00,
# which needs no toggle, and every later layer decides its own default when it lands.
DEFAULT_ENABLED_SOURCES: tuple[ToggleableMemorySystemId, ...] = ()


@dataclass(frozen=True, slots=True)
class MemorySettings:
    enabled_sources: tuple[ToggleableMemorySystemId, ...] = DEFAULT_ENABLED_SOURCES

    def is_enabled(self, source_id: MemorySystemId) -> bool:
        """Layer 00 is always on; the rest answer from the enabled set."""
        if source_id == "recent_window":
            return True
        return source_id in self.enabled_sources

    def with_source_enabled(self, source_id: ToggleableMemorySystemId) -> "MemorySettings":
        if source_id in self.enabled_sources:
            return self
        return replace(self, enabled_sources=(*self.enabled_sources, source_id))

    def with_source_disabled(self, source_id: ToggleableMemorySystemId) -> "MemorySettings":
        remaining = tuple(enabled for enabled in self.enabled_sources if enabled != source_id)
        if len(remaining) == len(self.enabled_sources):
            return self
        return replace(self, enabled_sources=remaining)
