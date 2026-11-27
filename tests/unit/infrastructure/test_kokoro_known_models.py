import logging

import pytest

from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.speech.kokoro_synthesizer import (
    KokoroSpeechSynthesizer,
    build_speech_synthesizer,
)


@pytest.mark.parametrize("model", ["hexgrad/Kokoro-82M", "hexgrad/Kokoro-82M-v1.1-zh"])
def test_the_known_model_ids_are_accepted(model: str) -> None:
    synthesizer = build_speech_synthesizer(
        Settings(speech_model=model), package_installed=lambda: True
    )

    assert isinstance(synthesizer, KokoroSpeechSynthesizer)


def test_an_unknown_model_id_turns_speech_off_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(speech_model="someone/other-model")

    with caplog.at_level(logging.WARNING):
        synthesizer = build_speech_synthesizer(settings, package_installed=lambda: True)

    assert synthesizer is None
    assert "hexgrad/Kokoro-82M" in caplog.text
