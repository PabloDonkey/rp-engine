import asyncio
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rp_engine.adapters.api import create_admin_router
from rp_engine.app.main import create_app
from rp_engine.core.ports.speech_synthesizer import InsufficientGpuMemoryError
from rp_engine.infrastructure.config.settings import Settings

WAV = b"RIFF....WAVEfake"


class FakeSynthesizer:
    def __init__(self, *, delay: float = 0.0, error: Exception | None = None) -> None:
        self.delay = delay
        self.error = error
        self.texts: list[str] = []
        self.running = 0
        self.max_running = 0
        self._guard = threading.Lock()

    def synthesize(self, text: str) -> bytes:
        with self._guard:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        try:
            time.sleep(self.delay)
            self.texts.append(text)
            if self.error is not None:
                raise self.error
            return WAV
        finally:
            with self._guard:
                self.running -= 1


def _app(synthesizer: FakeSynthesizer | None) -> FastAPI:
    app = FastAPI()
    app.include_router(
        create_admin_router(
            admin_service=None,  # type: ignore[arg-type]
            telegram_authorization=None,
            scenario_transfer_service=None,  # type: ignore[arg-type]
            playthrough_service=None,  # type: ignore[arg-type]
            speech_synthesizer=synthesizer,
        )
    )
    return app


def test_speech_returns_wav_bytes() -> None:
    synthesizer = FakeSynthesizer()
    client = TestClient(_app(synthesizer))

    response = client.post("/admin/speech", json={"text": "The door creaks."})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == WAV
    assert synthesizer.texts == ["The door creaks."]


def test_speech_answers_503_when_not_enabled() -> None:
    client = TestClient(_app(None))

    response = client.post("/admin/speech", json={"text": "Hello."})

    assert response.status_code == 503
    assert response.json() == {"detail": "Speech is not enabled"}


def test_speech_answers_503_when_the_card_has_too_little_memory() -> None:
    client = TestClient(_app(FakeSynthesizer(error=InsufficientGpuMemoryError())))

    response = client.post("/admin/speech", json={"text": "Hello."})

    assert response.status_code == 503
    assert response.json() == {"detail": "Not enough graphics card memory"}


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_speech_rejects_empty_text(text: str) -> None:
    synthesizer = FakeSynthesizer()
    client = TestClient(_app(synthesizer))

    response = client.post("/admin/speech", json={"text": text})

    assert response.status_code == 422
    assert synthesizer.texts == []


def test_speech_rejects_a_missing_text_field() -> None:
    client = TestClient(_app(FakeSynthesizer()))

    assert client.post("/admin/speech", json={}).status_code == 422


@pytest.mark.asyncio
async def test_two_requests_never_generate_at_the_same_time() -> None:
    synthesizer = FakeSynthesizer(delay=0.05)
    transport = httpx.ASGITransport(app=_app(synthesizer))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first, second = await asyncio.gather(
            client.post("/admin/speech", json={"text": "One."}),
            client.post("/admin/speech", json={"text": "Two."}),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert sorted(synthesizer.texts) == ["One.", "Two."]
    assert synthesizer.max_running == 1


def test_the_app_has_no_synthesizer_when_speech_is_off(tmp_path: Path) -> None:
    settings = Settings(
        telegram_enabled=False,
        telegram_authorization_dir=str(tmp_path / "authorization"),
        postgres_host="127.0.0.1",
        postgres_port=1,
        postgres_startup_check_fail_fast=False,
        speech_model="",
    )
    client = TestClient(create_app(settings))

    response = client.post("/admin/speech", json={"text": "Hello."})

    assert response.status_code == 503
    assert response.json() == {"detail": "Speech is not enabled"}
