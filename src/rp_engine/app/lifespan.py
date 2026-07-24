import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

logger = logging.getLogger(__name__)


class TelegramRuntimeProtocol(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class DbHealthProbeProtocol(Protocol):
    async def ping(self) -> bool: ...

    async def check_schema_version(self) -> None: ...


class ContainerProtocol(Protocol):
    @property
    def telegram_runtime(self) -> TelegramRuntimeProtocol | None: ...

    @property
    def runtime_state(self) -> "RuntimeStateProtocol": ...

    @property
    def db_health_probe(self) -> DbHealthProbeProtocol | None: ...

    @property
    def db_startup_check_fail_fast(self) -> bool: ...


class RuntimeStateProtocol(Protocol):
    app_state: str


def create_lifespan(
    container: ContainerProtocol,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        container.runtime_state.app_state = "starting"
        logger.info("Application runtime starting")

        if container.db_health_probe is not None:
            if await container.db_health_probe.ping():
                logger.info("PostgreSQL connectivity check passed")
                await container.db_health_probe.check_schema_version()
            else:
                logger.error("PostgreSQL is unreachable at startup")
                if container.db_startup_check_fail_fast:
                    raise RuntimeError(
                        "PostgreSQL is unreachable at startup. Set "
                        "RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST=false to boot anyway."
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
