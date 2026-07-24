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
    db_health_probe: "FakeDbHealthProbe | None" = None
    db_startup_check_fail_fast: bool = True


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


class FakeDbHealthProbe:
    def __init__(self, *, reachable: bool) -> None:
        self.reachable = reachable
        self.schema_checked = False

    async def ping(self) -> bool:
        return self.reachable

    async def check_schema_version(self) -> None:
        self.schema_checked = True


@pytest.mark.asyncio
async def test_lifespan_checks_schema_version_when_db_reachable() -> None:
    probe = FakeDbHealthProbe(reachable=True)
    container = FakeContainer(
        telegram_runtime=None, runtime_state=RuntimeState(), db_health_probe=probe
    )

    lifespan = create_lifespan(container)
    async with lifespan(FastAPI()):
        assert probe.schema_checked is True
        assert container.runtime_state.app_state == "running"


@pytest.mark.asyncio
async def test_lifespan_raises_when_db_unreachable_and_fail_fast() -> None:
    probe = FakeDbHealthProbe(reachable=False)
    container = FakeContainer(
        telegram_runtime=None,
        runtime_state=RuntimeState(),
        db_health_probe=probe,
        db_startup_check_fail_fast=True,
    )

    lifespan = create_lifespan(container)
    with pytest.raises(RuntimeError, match="unreachable"):
        async with lifespan(FastAPI()):
            pass


@pytest.mark.asyncio
async def test_lifespan_continues_when_db_unreachable_and_not_fail_fast() -> None:
    telegram_runtime = FakeTelegramRuntime()
    probe = FakeDbHealthProbe(reachable=False)
    container = FakeContainer(
        telegram_runtime=telegram_runtime,
        runtime_state=RuntimeState(),
        db_health_probe=probe,
        db_startup_check_fail_fast=False,
    )

    lifespan = create_lifespan(container)
    async with lifespan(FastAPI()):
        assert container.runtime_state.app_state == "running"
        assert telegram_runtime.started is True
