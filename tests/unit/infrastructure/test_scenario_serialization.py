from uuid import UUID

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
    assert directives.director_instruction == ""
