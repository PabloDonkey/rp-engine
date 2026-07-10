from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI


class TelegramRuntimeProtocol(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class ContainerProtocol(Protocol):
    @property
    def telegram_runtime(self) -> TelegramRuntimeProtocol | None: ...


def create_lifespan(
    container: ContainerProtocol,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if container.telegram_runtime is not None:
            await container.telegram_runtime.start()

        try:
            yield
        finally:
            if container.telegram_runtime is not None:
                await container.telegram_runtime.stop()

    return lifespan
