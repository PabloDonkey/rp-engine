import pytest

from rp_engine.core.scenario.user_persona import parse_persona_reply


def test_first_line_is_the_name_and_the_rest_is_the_description() -> None:
    name, description = parse_persona_reply(
        "Sera Vane\nA wary courier who trusts machines.\nLoves rain, hates crowds."
    )

    assert name == "Sera Vane"
    assert description == "A wary courier who trusts machines.\nLoves rain, hates crowds."


def test_a_single_line_is_a_name_with_no_description() -> None:
    assert parse_persona_reply("Kes") == ("Kes", "")


def test_surrounding_whitespace_is_trimmed_from_both_parts() -> None:
    assert parse_persona_reply("  Kes  \n\n  A drifter.  \n") == ("Kes", "A drifter.")


def test_leading_blank_lines_do_not_shift_the_name_into_the_description() -> None:
    assert parse_persona_reply("\n\nKes\nA drifter.") == ("Kes", "A drifter.")


@pytest.mark.parametrize("text", ["", "   ", "\n", "\n \n"])
def test_a_blank_reply_is_rejected_rather_than_treated_as_a_skip(text: str) -> None:
    # Skipping is an explicit command at the transport, so the parser never has to guess
    # what an empty or short message was "meant" to be.
    with pytest.raises(ValueError):
        parse_persona_reply(text)
