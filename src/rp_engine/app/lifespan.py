import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

logger = logging.getLogger(__name__)


class TelegramRuntimeProtocol(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class ContainerProtocol(Protocol):
    @property
    def telegram_runtime(self) -> TelegramRuntimeProtocol | None: ...

    @property
    def runtime_state(self) -> "RuntimeStateProtocol": ...


class RuntimeStateProtocol(Protocol):
    app_state: str


def create_lifespan(
    container: ContainerProtocol,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        container.runtime_state.app_state = "starting"
        if container.telegram_runtime is not None:
            await container.telegram_runtime.start()
            logger.info("Telegram adapter started")

        container.runtime_state.app_state = "running"

        try:
            yield
        finally:
            container.runtime_state.app_state = "stopping"
            if container.telegram_runtime is not None:
                await container.telegram_runtime.stop()
            container.runtime_state.app_state = "stopped"

    return lifespan
