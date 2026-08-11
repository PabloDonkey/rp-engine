from typing import Protocol

from rp_engine.core.memory.fragment import MemoryFragment, MemorySystemId
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecallContext


class MemorySource(Protocol):
    """One memory layer. Five of them exist; each one fails where the next one covers.

    The port has two halves with different costs (ADR-026):

    * `recall` runs before the prompt is built, on the turn path, so it must be fast.
    * `observe` runs after a successful turn, in the background worker, so it may be slow.
      It receives identifiers only and re-reads what it needs.

    A source reports what its fragments cost. It never decides whether they fit, and it
    never writes to the prompt. A source that raises must not fail the turn — the pipeline
    logs it and carries on without it — but a source that can return nothing should prefer
    returning nothing.
    """

    id: MemorySystemId

    async def recall(self, context: MemoryRecallContext) -> tuple[MemoryFragment, ...]: ...

    async def observe(self, context: MemoryObserveContext) -> None: ...
