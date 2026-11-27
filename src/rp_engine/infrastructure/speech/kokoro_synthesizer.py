import importlib.util
import io
import logging
import sys
import wave
from array import array
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import Protocol

from rp_engine.core.ports.speech_synthesizer import InsufficientGpuMemoryError, SpeechSynthesizer
from rp_engine.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

_MIB = 1024 * 1024
_PCM_MAX = 32767
# The repository IDs that kokoro knows. `KModel` looks the ID up in a fixed table, so any
# other value fails with a KeyError on the first request.
KNOWN_MODELS = ("hexgrad/Kokoro-82M", "hexgrad/Kokoro-82M-v1.1-zh")
SAMPLE_RATE = 24000  # Kokoro always makes 24 kHz audio.


class SpeechPipeline(Protocol):
    """Text and voice in, audio chunks out. Each chunk is a list of float samples."""

    def __call__(self, text: str, voice: str) -> Iterable[Sequence[float]]: ...


def _load_kokoro_pipeline(model_name: str, lang_code: str) -> SpeechPipeline:
    # Imported here, not at the top of the file: torch and kokoro belong to the optional
    # `speech` extra. The module must import (and mypy and the tests must run) without them.
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=lang_code, repo_id=model_name, device="cuda")

    def run(text: str, voice: str) -> Iterator[Sequence[float]]:
        for result in pipeline(text, voice=voice):
            if result.audio is not None:
                # A torch tensor is slow to walk in Python. `tolist()` makes plain floats.
                yield result.audio.tolist()

    return run


def _free_gpu_memory_mib() -> int:
    import torch

    free_bytes, _total_bytes = torch.cuda.mem_get_info()
    return int(free_bytes // _MIB)


def _to_wav_bytes(samples: Sequence[float], sample_rate: int) -> bytes:
    """Write float samples in the range -1 to 1 as a mono, 16-bit PCM WAV file."""
    pcm = array(
        "h",
        (round(max(-1.0, min(1.0, float(sample))) * _PCM_MAX) for sample in samples),
    )
    if sys.byteorder == "big":
        pcm.byteswap()  # WAV data is little-endian.
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


class KokoroSpeechSynthesizer:
    """Speaks text with Kokoro-82M on the local graphics card.

    The pipeline loads on the first request and then stays loaded. Before the load, the
    adapter checks free graphics card memory, so a busy card (for example one that is
    running LM Studio) gives a clear error instead of a crash.

    Both the loader and the memory query can be replaced, so tests run without torch.
    """

    def __init__(
        self,
        *,
        model_name: str,
        voice: str,
        lang_code: str,
        min_free_mib: int,
        load_pipeline: Callable[[str, str], SpeechPipeline] = _load_kokoro_pipeline,
        free_memory_mib: Callable[[], int] = _free_gpu_memory_mib,
    ) -> None:
        self._model_name = model_name
        self._voice = voice
        self._lang_code = lang_code
        self._min_free_mib = min_free_mib
        self._load_pipeline = load_pipeline
        self._free_memory_mib = free_memory_mib
        self._pipeline: SpeechPipeline | None = None

    def synthesize(self, text: str) -> bytes:
        pipeline = self._loaded_pipeline()
        samples: list[float] = []
        for chunk in pipeline(text, self._voice):
            samples.extend(chunk)
        return _to_wav_bytes(samples, SAMPLE_RATE)

    def _loaded_pipeline(self) -> SpeechPipeline:
        if self._pipeline is not None:
            return self._pipeline
        free_mib = self._free_memory_mib()
        if free_mib < self._min_free_mib:
            logger.warning(
                "Speech model not loaded: too little free graphics card memory",
                extra={"free_mib": free_mib, "min_free_mib": self._min_free_mib},
            )
            raise InsufficientGpuMemoryError()
        logger.info("Loading speech model", extra={"model": self._model_name})
        self._pipeline = self._load_pipeline(self._model_name, self._lang_code)
        return self._pipeline


def _kokoro_installed() -> bool:
    return importlib.util.find_spec("kokoro") is not None


def build_speech_synthesizer(
    settings: Settings,
    *,
    package_installed: Callable[[], bool] = _kokoro_installed,
) -> SpeechSynthesizer | None:
    """Return the synthesizer, or None when speech is off or the `speech` extra is missing.

    This loads nothing. The model loads on the first request.
    """
    if not settings.speech_model:
        logger.info("Speech disabled")
        return None
    if settings.speech_model not in KNOWN_MODELS:
        logger.warning(
            "RP_ENGINE_SPEECH_MODEL is not a model that kokoro knows; use one of %s. "
            "Speech disabled.",
            ", ".join(KNOWN_MODELS),
        )
        return None
    if not package_installed():
        logger.warning(
            "RP_ENGINE_SPEECH_MODEL is set, but kokoro is not installed; "
            "run `uv sync --extra speech`. Speech disabled."
        )
        return None
    logger.info("Speech enabled", extra={"model": settings.speech_model})
    return KokoroSpeechSynthesizer(
        model_name=settings.speech_model,
        voice=settings.speech_voice,
        lang_code=settings.speech_lang_code,
        min_free_mib=settings.speech_min_free_mib,
    )
