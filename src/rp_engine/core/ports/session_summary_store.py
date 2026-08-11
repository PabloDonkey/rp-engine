from typing import Protocol
from uuid import UUID

from rp_engine.core.memory.session_summary import SessionSummary


class SessionSummaryStore(Protocol):
    """Where layer 01 keeps the running recap. One row per session.

    `save` is an upsert: a session has at most one recap, and every pass rewrites it in
    place rather than appending a version. History of the recap itself is not kept — the
    transcript it was made from already is.
    """

    async def get(self, session_id: UUID) -> SessionSummary | None: ...

    async def save(self, summary: SessionSummary) -> SessionSummary: ...
