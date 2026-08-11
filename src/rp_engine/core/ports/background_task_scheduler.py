from collections.abc import Awaitable, Callable
from typing import Protocol

# What the scheduler runs: a zero-argument coroutine function. Everything the job needs is
# captured when it is built, and it must be a *question about stored state* rather than a
# command carrying data (ADR-026 decision 1) — that is what makes a job lost to a restart
# harmless, because the next turn asks the same question.
BackgroundJob = Callable[[], Awaitable[None]]


class BackgroundTaskScheduler(Protocol):
    """Runs work off the turn path, inside the same process.

    `submit` returns at once, so the player never waits for it. It answers whether the job
    was accepted: a job for a key that already has one in flight is dropped, and so is one
    that arrives when the queue is full. Both are safe, because a dropped job is
    re-derivable — the next turn submits the same question.

    Nothing here is durable. There is no jobs table, no lease and no retry policy, and
    ADR-026 explains why none of them is needed.
    """

    def submit(self, *, key: str, job: BackgroundJob) -> bool: ...
