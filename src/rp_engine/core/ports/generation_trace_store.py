from typing import Protocol
from uuid import UUID


class GenerationTraceStore(Protocol):
    async def append(self, *, session_id: UUID, record: dict[str, object]) -> None: ...

    async def list_for_session(self, session_id: UUID) -> list[dict[str, object]]: ...

    async def delete_for_turn(self, *, session_id: UUID, turn: int) -> int:
        """Delete every trace recorded for one turn, returning how many were removed.

        A turn can hold more than one trace — each retry appends another — and all of them
        describe a turn that no longer exists once its message is deleted, so they go
        together.
        """
        ...
