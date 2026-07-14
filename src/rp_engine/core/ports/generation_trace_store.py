from typing import Protocol
from uuid import UUID


class GenerationTraceStore(Protocol):
    async def append(self, *, session_id: UUID, record: dict[str, object]) -> None: ...
