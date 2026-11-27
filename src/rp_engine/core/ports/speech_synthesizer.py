from typing import Protocol


class SpeechError(Exception):
    """A speech request failed in a way the caller can explain to the reader."""


class InsufficientGpuMemoryError(SpeechError):
    """The graphics card has too little free memory to load the speech model.

    Nothing was loaded. A later request may try again.
    """

    def __init__(self, message: str = "Not enough graphics card memory") -> None:
        super().__init__(message)


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Turn `text` into spoken audio and return it as WAV file bytes.

        This call blocks: it may load a model and run it on a graphics card. Call it from a
        worker thread, never from the event loop. It handles one text at a time.
        """
        ...
