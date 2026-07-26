import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from rp_engine.application.services.scenario_transfer_service import ImportReport

logger = logging.getLogger(__name__)


class TelegramRuntimeProtocol(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class DbHealthProbeProtocol(Protocol):
    async def ping(self) -> bool: ...

    async def check_schema_version(self) -> None: ...


class ScenarioTransferServiceProtocol(Protocol):
    async def import_directory(self, path: str) -> ImportReport: ...


class ContainerProtocol(Protocol):
    @property
    def telegram_runtime(self) -> TelegramRuntimeProtocol | None: ...

    @property
    def runtime_state(self) -> "RuntimeStateProtocol": ...

    @property
    def db_health_probe(self) -> DbHealthProbeProtocol: ...

    @property
    def db_startup_check_fail_fast(self) -> bool: ...

    @property
    def scenario_transfer_service(self) -> ScenarioTransferServiceProtocol: ...

    @property
    def scenario_catalog_dirs(self) -> "list[str]": ...


class RuntimeStateProtocol(Protocol):
    app_state: str


def create_lifespan(
    container: ContainerProtocol,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        container.runtime_state.app_state = "starting"
        logger.info("Application runtime starting")

        db_reachable = await container.db_health_probe.ping()
        if db_reachable:
            logger.info("PostgreSQL connectivity check passed")
            await container.db_health_probe.check_schema_version()
        else:
            logger.error("PostgreSQL is unreachable at startup")
            if container.db_startup_check_fail_fast:
                raise RuntimeError(
                    "PostgreSQL is unreachable at startup. Set "
                    "RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST=false to boot anyway."
                )

        # Only attempt this if the DB is actually reachable — otherwise this would raise
        # its own (unhandled) connection error right after the check above already logged
        # the same problem.
        if db_reachable:
            for directory in container.scenario_catalog_dirs:
                report = await container.scenario_transfer_service.import_directory(directory)
                logger.info(
                    "Curated scenario import complete",
                    extra={
                        "directory": directory,
                        "imported": report.imported,
                        "skipped": report.skipped,
                    },
                )

        if container.telegram_runtime is not None:
            await container.telegram_runtime.start()
            logger.info("Telegram adapter started")

        container.runtime_state.app_state = "running"
        logger.info("Application ready")

        try:
            yield
        finally:
            container.runtime_state.app_state = "stopping"
            logger.info("Application runtime stopping")
            if container.telegram_runtime is not None:
                await container.telegram_runtime.stop()
            container.runtime_state.app_state = "stopped"
            logger.info("Application stopped")

    return lifespan
