from dataclasses import dataclass, field

from rp_engine.core.metadata import Metadata


@dataclass(frozen=True, slots=True)
class StoryBeat:
    """
    A single node in an optional story graph.

    A beat is a narrative checkpoint (a scene, a decision point, an objective).
    Transitions map a named condition to the id of the next beat. Conditions are
    intentionally opaque strings at the domain level; how they are evaluated (LLM
    judgement, explicit user choice, world-state rule) is a runtime concern that is
    deliberately not modelled here yet.

    This type is pure data with no traversal behaviour. It exists so a scenario can
    optionally declare narrative structure without committing the engine to any
    particular story mechanic.
    """

    id: str
    description: str
    transitions: dict[str, str] = field(default_factory=dict)
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoryGraph:
    """
    Optional narrative structure for a scenario.

    The graph is a set of beats plus an entry point. It is part of the immutable
    scenario definition. Runtime progress through the graph (current beat, visited
    beats) is tracked separately in ScenarioSession.story_progress.

    A scenario with no narrative structure simply omits the story graph.
    """

    beats: dict[str, StoryBeat] = field(default_factory=dict)
    entry_beat_id: str | None = None
    metadata: Metadata = field(default_factory=dict)
