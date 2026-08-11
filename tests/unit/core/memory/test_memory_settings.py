from rp_engine.core.memory.settings import MemorySettings


def test_the_recent_window_is_always_on() -> None:
    # Layer 00 is the conversation itself, so there is no state in which it is off.
    assert MemorySettings().is_enabled("recent_window") is True


def test_a_layer_is_off_until_it_is_switched_on() -> None:
    settings = MemorySettings()

    assert settings.is_enabled("rolling_summary") is False
    assert settings.with_source_enabled("rolling_summary").is_enabled("rolling_summary") is True


def test_switching_a_layer_off_leaves_the_others_alone() -> None:
    settings = MemorySettings(enabled_sources=("rolling_summary", "lorebook"))

    remaining = settings.with_source_disabled("lorebook")

    assert remaining.enabled_sources == ("rolling_summary",)


def test_transitions_return_new_instances() -> None:
    settings = MemorySettings()

    settings.with_source_enabled("lorebook")

    assert settings.enabled_sources == ()


def test_enabling_a_layer_twice_changes_nothing() -> None:
    settings = MemorySettings(enabled_sources=("lorebook",))

    assert settings.with_source_enabled("lorebook") is settings


def test_disabling_a_layer_that_is_already_off_changes_nothing() -> None:
    settings = MemorySettings()

    assert settings.with_source_disabled("lorebook") is settings
