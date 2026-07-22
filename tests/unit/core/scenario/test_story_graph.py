import pytest

from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph


def test_story_beat_minimal():
    beat = StoryBeat(id="opening", description="The story begins")

    assert beat.id == "opening"
    assert beat.description == "The story begins"
    assert beat.transitions == {}
    assert beat.metadata == {}


def test_story_beat_with_transitions():
    beat = StoryBeat(
        id="crossroads",
        description="A fork in the road",
        transitions={"go_left": "forest", "go_right": "village"},
    )

    assert beat.transitions == {"go_left": "forest", "go_right": "village"}


def test_story_graph_empty():
    graph = StoryGraph()

    assert graph.beats == {}
    assert graph.entry_beat_id is None
    assert graph.metadata == {}


def test_story_graph_with_beats():
    opening = StoryBeat(id="opening", description="Start", transitions={"next": "end"})
    end = StoryBeat(id="end", description="Finish")
    graph = StoryGraph(
        beats={"opening": opening, "end": end},
        entry_beat_id="opening",
    )

    assert graph.entry_beat_id == "opening"
    assert graph.beats["opening"] is opening
    assert graph.beats["opening"].transitions["next"] == "end"


def test_story_graph_immutability():
    graph = StoryGraph(entry_beat_id="start")

    with pytest.raises(AttributeError):
        graph.entry_beat_id = "other"  # type: ignore
