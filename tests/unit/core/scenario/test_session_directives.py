import pytest

from rp_engine.core.scenario.session_directives import (
    LANGUAGE_AUTO,
    ScenarioRule,
    SessionDirectives,
    language_name,
    normalize_language,
)


def test_defaults_are_neutral() -> None:
    directives = SessionDirectives()

    assert directives.language == LANGUAGE_AUTO
    assert directives.rules == ()
    assert directives.director_instructions == ()
    assert directives.has_language_preference is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("fr", "fr"), ("FR", "fr"), ("  fr  ", "fr"), ("auto", "auto")],
)
def test_normalize_language_accepts_supported_codes(raw: str, expected: str) -> None:
    assert normalize_language(raw) == expected


@pytest.mark.parametrize("raw", ["klingon", "", "e", "french"])
def test_normalize_language_rejects_unsupported_codes(raw: str) -> None:
    assert normalize_language(raw) is None


def test_with_language_normalizes_and_replaces() -> None:
    directives = SessionDirectives().with_language("FR")

    assert directives.language == "fr"
    assert directives.has_language_preference is True
    assert language_name("fr") == "French"


def test_auto_is_not_a_language_preference() -> None:
    directives = SessionDirectives().with_language("fr").with_language("auto")

    assert directives.language == LANGUAGE_AUTO
    assert directives.has_language_preference is False


def test_with_language_rejects_unsupported_code() -> None:
    with pytest.raises(ValueError):
        SessionDirectives().with_language("klingon")


def test_rules_are_appended_with_incrementing_ids() -> None:
    directives, first = SessionDirectives().with_rule("  Keep replies short.  ")
    directives, second = directives.with_rule("No time skips.")

    assert first == ScenarioRule(id="1", text="Keep replies short.")
    assert second == ScenarioRule(id="2", text="No time skips.")
    assert directives.rules == (first, second)


def test_rule_ids_are_never_reused() -> None:
    """A player reading an id from `/rules` must keep pointing at the same rule after
    another rule is removed."""
    directives, first = SessionDirectives().with_rule("one")
    directives, second = directives.with_rule("two")

    trimmed = directives.without_rule(first.id)
    assert trimmed is not None
    trimmed, third = trimmed.with_rule("three")

    assert [rule.id for rule in trimmed.rules] == [second.id, "3"]
    assert third.id == "3"


def test_with_rule_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        SessionDirectives().with_rule("   ")


def test_without_rule_returns_none_for_unknown_id() -> None:
    directives, _ = SessionDirectives().with_rule("one")

    assert directives.without_rule("99") is None


def test_director_instruction_is_set_and_cleared() -> None:
    directives = SessionDirectives().with_director_instruction("  raise the stakes  ")
    assert directives.director_instructions == ("raise the stakes",)

    assert directives.without_director_instructions().director_instructions == ()


def test_director_instructions_stack_instead_of_replacing() -> None:
    """Several notes before one reply used to keep only the last, silently."""
    directives = (
        SessionDirectives()
        .with_director_instruction("Raise the stakes.")
        .with_director_instruction("Bring back the courier.")
        .with_director_instruction("End on a cliffhanger.")
    )

    assert directives.director_instructions == (
        "Raise the stakes.",
        "Bring back the courier.",
        "End on a cliffhanger.",
    )
    assert directives.has_director_instructions


def test_clearing_director_instructions_drops_the_whole_queue() -> None:
    """They all steered the same reply, so none of them outlives it."""
    directives = (
        SessionDirectives()
        .with_director_instruction("Raise the stakes.")
        .with_director_instruction("Bring back the courier.")
    )

    cleared = directives.without_director_instructions()

    assert cleared.director_instructions == ()
    assert not cleared.has_director_instructions


def test_director_instruction_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        SessionDirectives().with_director_instruction("  ")


def test_mutators_return_new_instances() -> None:
    original = SessionDirectives()
    updated, _ = original.with_language("fr").with_rule("one")

    assert original == SessionDirectives()
    assert updated != original
