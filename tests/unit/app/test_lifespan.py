import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI

from rp_engine.app.lifespan import create_lifespan
from rp_engine.app.runtime_state import RuntimeState
from rp_engine.application.services.scenario_transfer_service import ImportReport


class FakeTelegramRuntime:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class FakeDbHealthProbe:
    def __init__(self, *, reachable: bool = True) -> None:
        self.reachable = reachable
        self.schema_checked = False

    async def ping(self) -> bool:
        return self.reachable

    async def check_schema_version(self) -> None:
        self.schema_checked = True


class FakeScenarioTransferService:
    def __init__(self) -> None:
        self.imported_from: list[str] = []

    async def import_directory(self, path: str) -> ImportReport:
        self.imported_from.append(path)
        return ImportReport(imported=0, skipped=0)


class FakeTaskScheduler:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class FakeContextBudget:
    def __init__(self, *, total: int = 5734) -> None:
        self.total = total
        self.calls = 0

    async def total_tokens(self) -> int:
        self.calls += 1
        return self.total


@dataclass(slots=True)
class FakeContainer:
    telegram_runtime: FakeTelegramRuntime | None
    runtime_state: RuntimeState
    db_health_probe: FakeDbHealthProbe = field(default_factory=FakeDbHealthProbe)
    db_startup_check_fail_fast: bool = True
    scenario_transfer_service: FakeScenarioTransferService = field(
        default_factory=FakeScenarioTransferService
    )
    scenario_catalog_dirs: list[str] = field(default_factory=lambda: ["data/catalog"])
    context_budget: FakeContextBudget = field(default_factory=FakeContextBudget)
    task_scheduler: FakeTaskScheduler = field(default_factory=FakeTaskScheduler)


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
async def test_lifespan_imports_curated_scenarios_when_db_reachable() -> None:
    transfer_service = FakeScenarioTransferService()
    container = FakeContainer(
        telegram_runtime=None,
        runtime_state=RuntimeState(),
        scenario_transfer_service=transfer_service,
        scenario_catalog_dirs=["data/catalog", "data/catalog-local"],
    )

    lifespan = create_lifespan(container)
    async with lifespan(FastAPI()):
        pass

    assert transfer_service.imported_from == ["data/catalog", "data/catalog-local"]


@pytest.mark.asyncio
async def test_lifespan_resolves_the_context_token_budget(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Reading the budget at boot is what puts a wrong one in the log, instead of leaving it
    # to silently drop story on the first turn.
    budget = FakeContextBudget(total=5734)
    container = FakeContainer(
        telegram_runtime=None,
        runtime_state=RuntimeState(),
        context_budget=budget,
    )

    lifespan = create_lifespan(container)
    with caplog.at_level(logging.INFO):
        async with lifespan(FastAPI()):
            pass

    assert budget.calls == 1
    assert "Context token budget resolved" in caplog.text


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
    transfer_service = FakeScenarioTransferService()
    container = FakeContainer(
        telegram_runtime=telegram_runtime,
        runtime_state=RuntimeState(),
        db_health_probe=probe,
        db_startup_check_fail_fast=False,
        scenario_transfer_service=transfer_service,
    )

    lifespan = create_lifespan(container)
    async with lifespan(FastAPI()):
        assert container.runtime_state.app_state == "running"
        assert telegram_runtime.started is True

    # The import step never even tries to run when the DB is unreachable — otherwise it
    # would raise its own connection error right after the health check already logged it.
    assert transfer_service.imported_from == []
