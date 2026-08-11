"""The in-process background worker (ADR-026 decision 1).

Three pieces, all inside the running process: a bounded `asyncio.Queue`, one worker loop
that `app/lifespan.py` starts next to the Telegram runtime, and a `submit` that returns at
once so the turn pays nothing.

There is no jobs table, no lease and no retry policy, and none is missing. A job is a
question about stored state, so a job lost to a restart costs nothing — the next turn asks
the same question and the worker catches up.
"""

import asyncio
import logging

from rp_engine.core.ports.background_task_scheduler import BackgroundJob, BackgroundTaskScheduler

logger = logging.getLogger(__name__)

# How many questions may wait at once. Small on purpose: the queue holds work for sessions
# that are being played right now, and a backlog longer than this means the worker cannot
# keep up, which dropping tells us and buffering hides.
DEFAULT_MAX_QUEUE_SIZE = 64


class AsyncioTaskScheduler(BackgroundTaskScheduler):
    def __init__(self, *, max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE) -> None:
        self._queue: asyncio.Queue[tuple[str, BackgroundJob]] = asyncio.Queue(
            maxsize=max_queue_size
        )
        # The keys that are queued or running. It is what makes two fast turns of the same
        # session produce one job instead of two writers racing over the same row.
        self._in_flight: set[str] = set()
        self._worker: asyncio.Task[None] | None = None

    def submit(self, *, key: str, job: BackgroundJob) -> bool:
        if self._worker is None:
            logger.debug("Background scheduler is not running; dropping job %s.", key)
            return False
        if key in self._in_flight:
            # Not a failure: the job already queued asks the same question, and it will
            # read the state this turn just wrote.
            logger.debug("Background job %s is already in flight; dropping the duplicate.", key)
            return False
        try:
            self._queue.put_nowait((key, job))
        except asyncio.QueueFull:
            logger.warning(
                "Background queue is full; dropping job %s. The next turn re-submits it.",
                key,
                extra={"job_key": key, "queue_size": self._queue.maxsize},
            )
            return False
        self._in_flight.add(key)
        return True

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = asyncio.create_task(self._run(), name="background-task-scheduler")
        logger.info("Background task scheduler started")

    async def stop(self) -> None:
        """Cancel the worker rather than drain it.

        Draining would block a restart on a model call that can take thirty seconds, for
        work the next turn redoes anyway.
        """
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        self._in_flight.clear()
        logger.info("Background task scheduler stopped")

    async def _run(self) -> None:
        while True:
            key, job = await self._queue.get()
            try:
                await job()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Implementation rule 4 applied to the write half: a failed job is logged
                # and swallowed. It reaches no player, and the next turn asks again.
                logger.exception("Background job %s failed.", key, extra={"job_key": key})
            finally:
                self._in_flight.discard(key)
                self._queue.task_done()
