from uuid import UUID

import pytest

from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import ScenarioRule, SessionDirectives
from rp_engine.infrastructure.scenario_serialization import (
    scenario_session_from_payload,
    scenario_session_to_payload,
    session_directives_from_payload,
    session_directives_to_payload,
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
