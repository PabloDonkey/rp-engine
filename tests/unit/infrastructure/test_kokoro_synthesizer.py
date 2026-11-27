import io
import wave
from collections.abc import Sequence

import pytest
from rp_engine.infrastructure.speech.kokoro_synthesizer import (
    KokoroSpeechSynthesizer,
    build_speech_synthesizer,
)

from rp_engine.core.ports.speech_synthesizer import (
    InsufficientGpuMemoryError,
    SpeechSynthesizer,
)
from rp_engine.infrastructure.config.settings import Settings


class FakePipeline:
    """Stands in for the Kokoro pipeline: text and voice in, audio chunks out. No torch."""

    def __init__(self, chunks: list[list[float]]) -> None:
        self.chunks = chunks
        self.calls: list[tuple[str, str]] = []

    def __call__(self, text: str, voice: str) -> list[Sequence[float]]:
        self.calls.append((text, voice))
        return list(self.chunks)


class Loader:
    def __init__(self, pipeline: FakePipeline) -> None:
        self.pipeline = pipeline
        self.loads: list[tuple[str, str]] = []

    def __call__(self, model_name: str, lang_code: str) -> FakePipeline:
        self.loads.append((model_name, lang_code))
        return self.pipeline


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
    min_free_mib: int = 1500,
) -> KokoroSpeechSynthesizer:
    return KokoroSpeechSynthesizer(
        model_name="hexgrad/test-model",
        voice="am_michael",
        lang_code="a",
        min_free_mib=min_free_mib,
        load_pipeline=loader,
        free_memory_mib=free if free is not None else FreeMemory(8000),
    )


def _samples(audio: bytes, count: int) -> list[int]:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        frames = wav.readframes(count)
    return [
        int.from_bytes(frames[i : i + 2], "little", signed=True) for i in range(0, count * 2, 2)
    ]


def test_synthesize_returns_a_24khz_mono_wav_file() -> None:
    loader = Loader(FakePipeline([[0.0, 0.5, -0.5, 1.0]]))

    audio = _synthesizer(loader).synthesize("Hello there.")

    with wave.open(io.BytesIO(audio), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 24000
        assert wav.getnframes() == 4
    values = _samples(audio, 4)
    assert values[0] == 0
    assert values[3] == 32767
    assert values[1] > 0 > values[2]


def test_the_chunks_are_joined_in_order() -> None:
    loader = Loader(FakePipeline([[1.0], [0.0, -1.0], [1.0]]))

    audio = _synthesizer(loader).synthesize("First line.\nSecond line.")

    assert _samples(audio, 4) == [32767, 0, -32767, 32767]


def test_samples_outside_the_range_are_clipped() -> None:
    loader = Loader(FakePipeline([[3.0, -3.0]]))

    audio = _synthesizer(loader).synthesize("Loud.")

    assert _samples(audio, 2) == [32767, -32767]


def test_the_pipeline_gets_the_text_and_the_configured_voice() -> None:
    pipeline = FakePipeline([[0.0]])

    _synthesizer(Loader(pipeline)).synthesize("Hello there.")

    assert pipeline.calls == [("Hello there.", "am_michael")]


def test_nothing_is_loaded_until_the_first_request() -> None:
    loader = Loader(FakePipeline([[0.0]]))

    _synthesizer(loader)

    assert loader.loads == []


def test_the_pipeline_loads_once_with_the_model_and_language() -> None:
    loader = Loader(FakePipeline([[0.0]]))
    synthesizer = _synthesizer(loader)

    synthesizer.synthesize("One.")
    synthesizer.synthesize("Two.")

    assert loader.loads == [("hexgrad/test-model", "a")]


def test_too_little_free_memory_raises_and_loads_nothing() -> None:
    loader = Loader(FakePipeline([[0.0]]))
    synthesizer = _synthesizer(loader, FreeMemory(1499), min_free_mib=1500)

    with pytest.raises(InsufficientGpuMemoryError, match="Not enough graphics card memory"):
        synthesizer.synthesize("Hello.")

    assert loader.loads == []


def test_exactly_the_minimum_free_memory_is_enough() -> None:
    loader = Loader(FakePipeline([[0.0]]))

    _synthesizer(loader, FreeMemory(1500), min_free_mib=1500).synthesize("Hello.")

    assert loader.loads == [("hexgrad/test-model", "a")]


def test_a_later_request_tries_again_after_a_memory_failure() -> None:
    loader = Loader(FakePipeline([[0.0]]))
    free = FreeMemory(100)
    synthesizer = _synthesizer(loader, free)

    with pytest.raises(InsufficientGpuMemoryError):
        synthesizer.synthesize("Hello.")
    free.mib = 9000
    audio = synthesizer.synthesize("Hello.")

    assert audio.startswith(b"RIFF")
    assert loader.loads == [("hexgrad/test-model", "a")]


def test_memory_is_not_checked_again_once_the_pipeline_is_loaded() -> None:
    free = FreeMemory(9000)
    synthesizer = _synthesizer(Loader(FakePipeline([[0.0]])), free)
    synthesizer.synthesize("One.")
    free.mib = 10  # The model itself now uses the memory.

    synthesizer.synthesize("Two.")


def test_the_adapter_satisfies_the_port() -> None:
    synthesizer: SpeechSynthesizer = _synthesizer(Loader(FakePipeline([[0.0]])))

    assert synthesizer.synthesize("Hi.").startswith(b"RIFF")


def test_no_synthesizer_when_the_model_setting_is_empty() -> None:
    settings = Settings(speech_model="")

    assert build_speech_synthesizer(settings, package_installed=lambda: True) is None


def test_no_synthesizer_when_the_package_is_missing() -> None:
    settings = Settings(speech_model="hexgrad/test-model")

    assert build_speech_synthesizer(settings, package_installed=lambda: False) is None


def test_a_synthesizer_is_built_when_enabled_and_the_package_is_present() -> None:
    settings = Settings(speech_model="hexgrad/test-model")

    synthesizer = build_speech_synthesizer(settings, package_installed=lambda: True)

    assert isinstance(synthesizer, KokoroSpeechSynthesizer)
