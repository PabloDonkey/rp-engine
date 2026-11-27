import pytest

from rp_engine.infrastructure.config.settings import Settings


def test_speech_is_off_by_default() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.speech_model == ""


def test_speech_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.speech_voice == "am_michael"
    assert settings.speech_lang_code == "a"
    assert settings.speech_min_free_mib == 1500


def test_the_qwen_settings_are_gone() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    for name in ("speech_speaker", "speech_instruct", "speech_language"):
        assert not hasattr(settings, name)


def test_speech_settings_read_the_rp_engine_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RP_ENGINE_SPEECH_MODEL", "hexgrad/test-model")
    monkeypatch.setenv("RP_ENGINE_SPEECH_VOICE", "af_heart")
    monkeypatch.setenv("RP_ENGINE_SPEECH_LANG_CODE", "b")
    monkeypatch.setenv("RP_ENGINE_SPEECH_MIN_FREE_MIB", "7000")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.speech_model == "hexgrad/test-model"
    assert settings.speech_voice == "af_heart"
    assert settings.speech_lang_code == "b"
    assert settings.speech_min_free_mib == 7000
