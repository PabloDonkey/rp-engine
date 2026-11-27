import importlib.util
import io
import logging
import sys
import wave
from array import array
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from rp_engine.core.ports.speech_synthesizer import InsufficientGpuMemoryError, SpeechSynthesizer
from rp_engine.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

_MIB = 1024 * 1024
_PCM_MAX = 32767


class SpeechModel(Protocol):
    """The part of `qwen_tts.Qwen3TTSModel` this adapter uses."""

    def generate_custom_voice(self, **kwargs: Any) -> tuple[Sequence[Sequence[float]], int]: ...


def _load_qwen_model(model_name: str) -> SpeechModel:
    # Imported here, not at the top of the file: torch and qwen_tts belong to the optional
    # `speech` extra. The module must import (and mypy and the tests must run) without them.
    import torch
    from qwen_tts import Qwen3TTSModel

    model: SpeechModel = Qwen3TTSModel.from_pretrained(
        model_name, device_map="cuda:0", dtype=torch.bfloat16
    )
    return model


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


class QwenSpeechSynthesizer:
    """Speaks text with Qwen3-TTS (CustomVoice) on the local graphics card.

    The model loads on the first request and then stays loaded. Before the load, the
    adapter checks free graphics card memory, so a busy card (for example one that is
    running LM Studio) gives a clear error instead of a crash.

    Both the loader and the memory query can be replaced, so tests run without torch.
    """

    def __init__(
        self,
        *,
        model_name: str,
        speaker: str,
        instruct: str,
        language: str,
        min_free_mib: int,
        load_model: Callable[[str], SpeechModel] = _load_qwen_model,
        free_memory_mib: Callable[[], int] = _free_gpu_memory_mib,
    ) -> None:
        self._model_name = model_name
        self._speaker = speaker
        self._instruct = instruct
        self._language = language
        self._min_free_mib = min_free_mib
        self._load_model = load_model
        self._free_memory_mib = free_memory_mib
        self._model: SpeechModel | None = None

    def synthesize(self, text: str) -> bytes:
        model = self._loaded_model()
        waves, sample_rate = model.generate_custom_voice(
            text=text,
            speaker=self._speaker,
            language=self._language,
            instruct=self._instruct,
            non_streaming_mode=True,
        )
        return _to_wav_bytes(waves[0], sample_rate)

    def _loaded_model(self) -> SpeechModel:
        if self._model is not None:
            return self._model
        free_mib = self._free_memory_mib()
        if free_mib < self._min_free_mib:
            logger.warning(
                "Speech model not loaded: too little free graphics card memory",
                extra={"free_mib": free_mib, "min_free_mib": self._min_free_mib},
            )
            raise InsufficientGpuMemoryError()
        logger.info("Loading speech model", extra={"model": self._model_name})
        self._model = self._load_model(self._model_name)
        return self._model


def _qwen_tts_installed() -> bool:
    return importlib.util.find_spec("qwen_tts") is not None


def build_speech_synthesizer(
    settings: Settings,
    *,
    package_installed: Callable[[], bool] = _qwen_tts_installed,
) -> SpeechSynthesizer | None:
    """Return the synthesizer, or None when speech is off or the `speech` extra is missing.

    This loads nothing. The model loads on the first request.
    """
    if not settings.speech_model:
        logger.info("Speech disabled")
        return None
    if not package_installed():
        logger.warning(
            "RP_ENGINE_SPEECH_MODEL is set, but qwen_tts is not installed; "
            "run `uv sync --extra speech`. Speech disabled."
        )
        return None
    logger.info("Speech enabled", extra={"model": settings.speech_model})
    return QwenSpeechSynthesizer(
        model_name=settings.speech_model,
        speaker=settings.speech_speaker,
        instruct=settings.speech_instruct,
        language=settings.speech_language,
        min_free_mib=settings.speech_min_free_mib,
    )
