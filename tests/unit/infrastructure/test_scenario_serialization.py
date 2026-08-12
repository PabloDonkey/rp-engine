from uuid import UUID

import pytest

from rp_engine.core.memory.fragment import ToggleableMemorySystemId
from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import ScenarioRule, SessionDirectives
from rp_engine.infrastructure.scenario_serialization import (
    memory_settings_from_payload,
    memory_settings_to_payload,
    metadata_from_payload,
    scenario_definition_from_payload,
    scenario_definition_to_payload,
    scenario_session_from_payload,
    scenario_session_to_payload,
    session_directives_from_payload,
    session_directives_to_payload,
    story_graph_from_payload,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000010")


def test_session_directives_round_trip() -> None:
    directives, _ = SessionDirectives().with_language("fr").with_rule("No time skips.")
    directives = directives.with_director_instruction("Raise the stakes.")

    restored = session_directives_from_payload(session_directives_to_payload(directives))

    assert restored == directives


@pytest.mark.parametrize("note_count", [0, 1, 3])
def test_director_instruction_queue_round_trips_at_any_length(note_count: int) -> None:
    directives = SessionDirectives()
    for index in range(note_count):
        directives = directives.with_director_instruction(f"Note {index}.")

    restored = session_directives_from_payload(session_directives_to_payload(directives))

    assert restored.director_instructions == directives.director_instructions


def test_pre_s020_single_note_payload_loads_as_a_one_element_queue() -> None:
    """A session *export file* written before the notes could stack still imports.

    Stored sessions were converted by migration `20260802_0011`; this covers the JSON
    transfer format, which outlives the schema it was dumped from.
    """
    directives = session_directives_from_payload(
        {"language": "fr", "rules": [], "director_instruction": "Raise the stakes."}
    )

    assert directives.director_instructions == ("Raise the stakes.",)


def test_pre_s020_empty_note_payload_loads_as_an_empty_queue() -> None:
    directives = session_directives_from_payload(
        {"language": "fr", "rules": [], "director_instruction": ""}
    )

    assert directives.director_instructions == ()


def test_scenario_session_round_trip_carries_directives() -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="vault",
        user_id=USER_ID,
        directives=SessionDirectives(language="fr", rules=(ScenarioRule(id="1", text="Brief."),)),
    )

    restored = scenario_session_from_payload(scenario_session_to_payload(session))

    assert restored == session


def test_missing_directives_payload_degrades_to_defaults() -> None:
    """Sessions written before the directives column exists must still load."""
    assert session_directives_from_payload(None) == SessionDirectives()
    assert session_directives_from_payload({}) == SessionDirectives()


def test_malformed_rules_are_skipped_rather_than_failing_the_load() -> None:
    directives = session_directives_from_payload(
        {
            "language": "fr",
            "rules": [{"id": "1", "text": "keep"}, {"id": "2"}, "nonsense"],
        }
    )

    assert directives.language == "fr"
    assert directives.rules == (ScenarioRule(id="1", text="keep"),)
    assert directives.director_instructions == ()


def test_scenario_session_round_trip_carries_the_persona_and_lifecycle() -> None:
    session = (
        ScenarioSession.create_for_user(scenario_definition_id="def-1", user_id=USER_ID)
        .with_persona(name="Sera Vane", description="A wary courier.")
        .mark_deleted()
    )

    restored = scenario_session_from_payload(scenario_session_to_payload(session))

    assert restored == session


def test_scenario_session_payload_without_the_persona_keeps_it_unset() -> None:
    session = ScenarioSession.create_for_user(scenario_definition_id="def-1", user_id=USER_ID)

    restored = scenario_session_from_payload(scenario_session_to_payload(session))

    assert restored is not None
    assert restored.user_persona_name is None
    assert restored.user_persona_description is None
    assert restored.deleted_at is None


def test_legacy_payloads_predating_the_lifecycle_fields_load_as_live() -> None:
    """Sessions exported before S015/S016 date from their creation and are not superseded —
    which is exactly what they were."""
    session = ScenarioSession.create_for_user(scenario_definition_id="def-1", user_id=USER_ID)
    payload = scenario_session_to_payload(session)
    for field in ("updated_at", "deleted_at", "user_persona_name", "user_persona_description"):
        payload.pop(field)

    restored = scenario_session_from_payload(payload)

    assert restored is not None
    assert restored.updated_at == session.created_at
    assert restored.deleted_at is None
    assert restored.user_persona_name is None


@pytest.mark.parametrize(
    "enabled",
    [
        (),
        ("rolling_summary",),
        ("rolling_summary", "lorebook", "fact_state", "semantic_recall"),
    ],
)
def test_memory_settings_round_trip(enabled: tuple[ToggleableMemorySystemId, ...]) -> None:
    settings = MemorySettings(enabled_sources=enabled)

    assert memory_settings_from_payload(memory_settings_to_payload(settings)) == settings


def test_scenario_session_round_trip_carries_the_memory_settings() -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="def-1",
        user_id=USER_ID,
        memory=MemorySettings(enabled_sources=("rolling_summary",)),
    )

    restored = scenario_session_from_payload(scenario_session_to_payload(session))

    assert restored is not None
    assert restored.memory == session.memory


def test_payloads_predating_the_memory_settings_load_with_the_defaults() -> None:
    """A session exported before S022 has no memory key and must still load."""
    session = ScenarioSession.create_for_user(scenario_definition_id="def-1", user_id=USER_ID)
    payload = scenario_session_to_payload(session)
    payload.pop("memory")

    restored = scenario_session_from_payload(payload)

    assert restored is not None
    assert restored.memory == MemorySettings()


def test_an_unknown_memory_layer_is_dropped_rather_than_kept() -> None:
    # Keeping it would let a stored payload smuggle in a value the type says cannot exist.
    restored = memory_settings_from_payload({"enabled_sources": ["rolling_summary", "telepathy"]})

    assert restored.enabled_sources == ("rolling_summary",)


@pytest.mark.parametrize("payload", [None, {}, {"enabled_sources": "rolling_summary"}])
def test_a_malformed_memory_payload_degrades_to_the_defaults(payload: object) -> None:
    assert memory_settings_from_payload(payload) == MemorySettings()  # type: ignore[arg-type]


def test_source_budgets_round_trip() -> None:
    settings = MemorySettings().with_source_budget("rolling_summary", 0.4)

    restored = memory_settings_from_payload(memory_settings_to_payload(settings))

    assert restored.budget_for("rolling_summary", 1000) == 400


def test_a_payload_without_source_budgets_loads_the_defaults() -> None:
    """A session stored by S022, before any layer had a share to defend."""
    restored = memory_settings_from_payload({"enabled_sources": ["rolling_summary"]})

    assert restored.source_budgets == MemorySettings().source_budgets


def test_a_share_outside_the_allowed_range_is_dropped() -> None:
    # The value object refuses to hold one, so keeping it would fail the whole load.
    restored = memory_settings_from_payload(
        {"enabled_sources": [], "source_budgets": {"rolling_summary": 4.0, "lorebook": 0.1}}
    )

    assert [budget.source for budget in restored.source_budgets] == ["lorebook"]


def test_an_unknown_layer_in_the_budgets_is_dropped() -> None:
    restored = memory_settings_from_payload(
        {"enabled_sources": [], "source_budgets": {"telepathy": 0.5}}
    )

    assert restored.source_budgets == ()


# --- metadata value model (S030 step 1) -------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param({"genre": "noir"}, {"genre": "noir"}, id="text-stays-text"),
        pytest.param(
            {"tags": ["noir", "heist"]}, {"tags": ["noir", "heist"]}, id="list-stays-a-list"
        ),
        pytest.param({"year": 1987}, {"year": "1987"}, id="a-number-becomes-text"),
        pytest.param({"rating": 4.5}, {"rating": "4.5"}, id="a-float-becomes-text"),
        pytest.param({"mature": True}, {"mature": "True"}, id="a-bool-becomes-text"),
        pytest.param({"tags": [1987, "noir"]}, {"tags": ["1987", "noir"]}, id="per-list-item"),
        pytest.param({"tags": []}, {"tags": []}, id="an-empty-list-stays-a-list"),
        pytest.param({"note": None}, {}, id="a-null-drops-its-key"),
        pytest.param({}, {}, id="an-empty-map-stays-empty"),
        pytest.param(None, {}, id="a-missing-map-reads-as-empty"),
    ],
)
def test_metadata_normalizer_table(raw: object, expected: dict[str, object]) -> None:
    assert metadata_from_payload(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param({"nested": {"deep": "value"}}, id="a-nested-object-fails"),
        pytest.param({"nested": [["deep"]]}, id="a-nested-list-fails"),
        pytest.param({"nested": [{"deep": "value"}]}, id="an-object-inside-a-list-fails"),
        pytest.param("not-a-map", id="a-non-object-map-fails"),
        pytest.param(["not-a-map"], id="a-list-in-place-of-the-map-fails"),
    ],
)
def test_metadata_shapes_with_no_control_fail(raw: object) -> None:
    with pytest.raises(ValueError):
        metadata_from_payload(raw)


def test_a_scenario_payload_with_a_tags_list_round_trips() -> None:
    """The real shape curated scenarios already store, which the old type denied."""
    payload = {
        "id": "vault",
        "owner_id": str(USER_ID),
        "name": "The Vault",
        "description": "A heist.",
        "world": {"id": "w", "name": "W", "description": "d", "metadata": {"era": ["1920s"]}},
        "characters": {
            "lead": {
                "id": "c",
                "name": "C",
                "description": "d",
                "personality": "p",
                "metadata": {"tags": ["thief"]},
            }
        },
        "metadata": {"tags": ["noir", "heist"], "year": 1987},
    }

    scenario = scenario_definition_from_payload(payload)

    assert scenario is not None
    assert scenario.metadata == {"tags": ["noir", "heist"], "year": "1987"}
    assert scenario.world is not None
    assert scenario.world.metadata == {"era": ["1920s"]}
    assert scenario.characters["lead"].metadata == {"tags": ["thief"]}
    assert scenario_definition_to_payload(scenario)["metadata"] == scenario.metadata


def test_a_scenario_payload_with_nested_metadata_is_refused() -> None:
    """A shape the form cannot draw fails the whole payload rather than loading half of it."""
    payload = {
        "id": "vault",
        "owner_id": str(USER_ID),
        "name": "The Vault",
        "description": "A heist.",
        "metadata": {"credits": {"writer": "someone"}},
    }

    assert scenario_definition_from_payload(payload) is None


def test_a_story_beat_carries_the_same_value_model() -> None:
    graph = story_graph_from_payload(
        {
            "entry_beat_id": "open",
            "beats": {"open": {"id": "open", "description": "d", "metadata": {"tags": ["act1"]}}},
            "metadata": {"acts": 3},
        }
    )

    assert graph is not None
    assert graph.metadata == {"acts": "3"}
    assert graph.beats["open"].metadata == {"tags": ["act1"]}
