import pytest

from rp_engine.infrastructure.config.settings import Settings


def test_speech_is_off_by_default() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.speech_model == ""


def test_speech_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.speech_speaker == "ryan"
    assert settings.speech_instruct == "A tense, quiet storyteller."
    assert settings.speech_language == "auto"
    assert settings.speech_min_free_mib == 4700


def test_speech_settings_read_the_rp_engine_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RP_ENGINE_SPEECH_MODEL", "Qwen/test-model")
    monkeypatch.setenv("RP_ENGINE_SPEECH_MIN_FREE_MIB", "7000")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.speech_model == "Qwen/test-model"
    assert settings.speech_min_free_mib == 7000
