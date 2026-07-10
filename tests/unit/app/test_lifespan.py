from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi import FastAPI

from rp_engine.app.lifespan import create_lifespan
from rp_engine.app.runtime_state import RuntimeState


class FakeTelegramRuntime:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


@dataclass(slots=True)
class FakeContainer:
    telegram_runtime: FakeTelegramRuntime | None
    runtime_state: RuntimeState


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_telegram_runtime() -> None:
    telegram_runtime = FakeTelegramRuntime()
    container = FakeContainer(telegram_runtime=telegram_runtime, runtime_state=RuntimeState())

    lifespan = create_lifespan(container)

    @asynccontextmanager
    async def _run_lifespan() -> AsyncIterator[None]:
        async with lifespan(FastAPI()):
            yield

    async with _run_lifespan():
        assert container.runtime_state.app_state == "running"
        assert telegram_runtime.started is True
        assert telegram_runtime.stopped is False

    assert container.runtime_state.app_state == "stopped"
    assert telegram_runtime.stopped is True
