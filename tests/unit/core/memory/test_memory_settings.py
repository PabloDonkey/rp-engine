from rp_engine.core.memory.settings import MemorySettings


def test_the_recent_window_is_always_on() -> None:
    # Layer 00 is the conversation itself, so there is no state in which it is off.
    assert MemorySettings().is_enabled("recent_window") is True


def test_the_rolling_summary_is_on_by_default() -> None:
    # A session that has to be told to remember is a session that already forgot.
    assert MemorySettings().is_enabled("rolling_summary") is True


def test_a_layer_is_off_until_it_is_switched_on() -> None:
    settings = MemorySettings()

    assert settings.is_enabled("lorebook") is False
    assert settings.with_source_enabled("lorebook").is_enabled("lorebook") is True


def test_switching_a_layer_off_leaves_the_others_alone() -> None:
    settings = MemorySettings(enabled_sources=("rolling_summary", "lorebook"))

    remaining = settings.with_source_disabled("lorebook")

    assert remaining.enabled_sources == ("rolling_summary",)


def test_transitions_return_new_instances() -> None:
    settings = MemorySettings(enabled_sources=())

    settings.with_source_enabled("lorebook")

    assert settings.enabled_sources == ()


def test_enabling_a_layer_twice_changes_nothing() -> None:
    settings = MemorySettings(enabled_sources=("lorebook",))

    assert settings.with_source_enabled("lorebook") is settings


def test_disabling_a_layer_that_is_already_off_changes_nothing() -> None:
    settings = MemorySettings(enabled_sources=())

    assert settings.with_source_disabled("lorebook") is settings


def test_a_layer_with_a_share_is_offered_only_that_share() -> None:
    settings = MemorySettings()

    assert settings.budget_for("rolling_summary", 1000) == 250


def test_a_layer_with_no_share_is_offered_what_the_shares_leave() -> None:
    # Layer 00 has no share of its own, so it gets the budget minus layer 01's quarter.
    # Without the subtraction the window would fill the budget and the priority cut would
    # drop the recap every turn, which would make a share mean nothing.
    assert MemorySettings().budget_for("recent_window", 1000) == 750


def test_a_disabled_layer_reserves_nothing() -> None:
    settings = MemorySettings(enabled_sources=())

    assert settings.budget_for("recent_window", 1000) == 1000


def test_a_layer_this_build_does_not_run_reserves_nothing() -> None:
    # A session switched a layer on against a newer build. It must not shrink the window
    # of a build that has no such layer to spend it.
    settings = MemorySettings()

    assert settings.budget_for("recent_window", 1000, among={"recent_window"}) == 1000


def test_a_share_never_exceeds_what_is_available() -> None:
    settings = MemorySettings().with_source_budget("rolling_summary", 1.0)

    assert settings.budget_for("rolling_summary", 40) == 40


def test_setting_a_share_replaces_the_one_it_had() -> None:
    settings = MemorySettings().with_source_budget("rolling_summary", 0.5)

    assert settings.budget_for("rolling_summary", 1000) == 500
    assert len(settings.source_budgets) == 1
