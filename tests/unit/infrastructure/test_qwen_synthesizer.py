import io
import wave
from typing import Any

import pytest

from rp_engine.core.ports.speech_synthesizer import (
    InsufficientGpuMemoryError,
    SpeechSynthesizer,
)
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.speech.qwen_synthesizer import (
    QwenSpeechSynthesizer,
    build_speech_synthesizer,
)


class FakeModel:
    """Stands in for `Qwen3TTSModel`: same call shape, no torch."""

    def __init__(self, samples: list[float], sample_rate: int = 24000) -> None:
        self.samples = samples
        self.sample_rate = sample_rate
        self.calls: list[dict[str, Any]] = []

    def generate_custom_voice(self, **kwargs: Any) -> tuple[list[list[float]], int]:
        self.calls.append(kwargs)
        return [self.samples], self.sample_rate


class Loader:
    def __init__(self, model: FakeModel) -> None:
        self.model = model
        self.names: list[str] = []

    def __call__(self, model_name: str) -> FakeModel:
        self.names.append(model_name)
        return self.model


class FreeMemory:
    """A memory query the test can change between requests."""

    def __init__(self, mib: int) -> None:
        self.mib = mib

    def __call__(self) -> int:
        return self.mib


def _synthesizer(
    loader: Loader,
    free: FreeMemory | None = None,
    *,
    min_free_mib: int = 5000,
) -> QwenSpeechSynthesizer:
    return QwenSpeechSynthesizer(
        model_name="Qwen/test-model",
        speaker="ryan",
        instruct="Quiet.",
        language="auto",
        min_free_mib=min_free_mib,
        load_model=loader,
        free_memory_mib=free if free is not None else FreeMemory(8000),
    )


def _samples(audio: bytes, count: int) -> list[int]:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        frames = wav.readframes(count)
    return [
        int.from_bytes(frames[i : i + 2], "little", signed=True) for i in range(0, count * 2, 2)
    ]


def test_synthesize_returns_a_wav_file_with_the_model_samples() -> None:
    loader = Loader(FakeModel([0.0, 0.5, -0.5, 1.0], sample_rate=16000))

    audio = _synthesizer(loader).synthesize("Hello there.")

    with wave.open(io.BytesIO(audio), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 4
    values = _samples(audio, 4)
    assert values[0] == 0
    assert values[3] == 32767
    assert values[1] > 0 > values[2]


def test_samples_outside_the_range_are_clipped() -> None:
    loader = Loader(FakeModel([3.0, -3.0]))

    audio = _synthesizer(loader).synthesize("Loud.")

    assert _samples(audio, 2) == [32767, -32767]


def test_the_model_gets_the_configured_voice() -> None:
    model = FakeModel([0.0])

    _synthesizer(Loader(model)).synthesize("Hello there.")

    (call,) = model.calls
    assert call["text"] == "Hello there."
    assert call["speaker"] == "ryan"
    assert call["language"] == "auto"
    assert call["instruct"] == "Quiet."
    assert call["non_streaming_mode"] is True


def test_nothing_is_loaded_until_the_first_request() -> None:
    loader = Loader(FakeModel([0.0]))

    _synthesizer(loader)

    assert loader.names == []


def test_the_model_loads_once_and_stays_loaded() -> None:
    loader = Loader(FakeModel([0.0]))
    synthesizer = _synthesizer(loader)

    synthesizer.synthesize("One.")
    synthesizer.synthesize("Two.")

    assert loader.names == ["Qwen/test-model"]


def test_too_little_free_memory_raises_and_loads_nothing() -> None:
    loader = Loader(FakeModel([0.0]))
    synthesizer = _synthesizer(loader, FreeMemory(4999), min_free_mib=5000)

    with pytest.raises(InsufficientGpuMemoryError, match="Not enough graphics card memory"):
        synthesizer.synthesize("Hello.")

    assert loader.names == []


def test_exactly_the_minimum_free_memory_is_enough() -> None:
    loader = Loader(FakeModel([0.0]))

    _synthesizer(loader, FreeMemory(5000), min_free_mib=5000).synthesize("Hello.")

    assert loader.names == ["Qwen/test-model"]


def test_a_later_request_tries_again_after_a_memory_failure() -> None:
    loader = Loader(FakeModel([0.0]))
    free = FreeMemory(1000)
    synthesizer = _synthesizer(loader, free)

    with pytest.raises(InsufficientGpuMemoryError):
        synthesizer.synthesize("Hello.")
    free.mib = 9000
    audio = synthesizer.synthesize("Hello.")

    assert audio.startswith(b"RIFF")
    assert loader.names == ["Qwen/test-model"]


def test_memory_is_not_checked_again_once_the_model_is_loaded() -> None:
    free = FreeMemory(9000)
    synthesizer = _synthesizer(Loader(FakeModel([0.0])), free)
    synthesizer.synthesize("One.")
    free.mib = 10  # The model itself now uses the memory.

    synthesizer.synthesize("Two.")


def test_the_adapter_satisfies_the_port() -> None:
    synthesizer: SpeechSynthesizer = _synthesizer(Loader(FakeModel([0.0])))

    assert synthesizer.synthesize("Hi.").startswith(b"RIFF")


def test_no_synthesizer_when_the_model_setting_is_empty() -> None:
    settings = Settings(speech_model="")

    assert build_speech_synthesizer(settings, package_installed=lambda: True) is None


def test_no_synthesizer_when_the_package_is_missing() -> None:
    settings = Settings(speech_model="Qwen/test-model")

    assert build_speech_synthesizer(settings, package_installed=lambda: False) is None


def test_a_synthesizer_is_built_when_enabled_and_the_package_is_present() -> None:
    settings = Settings(speech_model="Qwen/test-model")

    synthesizer = build_speech_synthesizer(settings, package_installed=lambda: True)

    assert isinstance(synthesizer, QwenSpeechSynthesizer)
