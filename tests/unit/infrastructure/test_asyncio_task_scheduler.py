import asyncio
import logging

import pytest

from rp_engine.infrastructure.tasks import AsyncioTaskScheduler


async def _settle() -> None:
    """Give the worker loop a turn of the event loop to pick the job up and finish it."""
    for _ in range(10):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_a_submitted_job_runs() -> None:
    scheduler = AsyncioTaskScheduler()
    await scheduler.start()
    done = asyncio.Event()

    async def job() -> None:
        done.set()

    assert scheduler.submit(key="memory:1", job=job) is True
    await asyncio.wait_for(done.wait(), timeout=1)
    await scheduler.stop()


@pytest.mark.asyncio
async def test_a_second_job_for_the_same_key_is_dropped() -> None:
    """Two fast turns of one session must produce one pass, not two writers racing.

    Dropping is safe because the job in flight asks the same question and reads the state
    this turn just wrote.
    """
    scheduler = AsyncioTaskScheduler()
    await scheduler.start()
    release = asyncio.Event()
    runs = 0

    async def job() -> None:
        nonlocal runs
        runs += 1
        await release.wait()

    assert scheduler.submit(key="memory:1", job=job) is True
    await _settle()
    assert scheduler.submit(key="memory:1", job=job) is False
    # A different session is unaffected.
    assert scheduler.submit(key="memory:2", job=job) is True

    release.set()
    await _settle()
    assert runs == 2
    await scheduler.stop()


@pytest.mark.asyncio
async def test_the_key_is_free_again_once_the_job_finishes() -> None:
    scheduler = AsyncioTaskScheduler()
    await scheduler.start()

    async def job() -> None:
        return None

    assert scheduler.submit(key="memory:1", job=job) is True
    await _settle()

    assert scheduler.submit(key="memory:1", job=job) is True
    await _settle()
    await scheduler.stop()


@pytest.mark.asyncio
async def test_a_job_that_raises_is_logged_and_does_not_stop_the_worker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    scheduler = AsyncioTaskScheduler()
    await scheduler.start()
    survived = asyncio.Event()

    async def failing() -> None:
        raise RuntimeError("the model said no")

    async def later() -> None:
        survived.set()

    with caplog.at_level(logging.ERROR):
        scheduler.submit(key="memory:1", job=failing)
        await _settle()
        scheduler.submit(key="memory:2", job=later)
        await asyncio.wait_for(survived.wait(), timeout=1)

    assert "the model said no" in caplog.text
    await scheduler.stop()


@pytest.mark.asyncio
async def test_a_full_queue_drops_rather_than_waits(caplog: pytest.LogCaptureFixture) -> None:
    """The turn path must never block on the queue. A dropped job is re-derivable."""
    scheduler = AsyncioTaskScheduler(max_queue_size=1)
    await scheduler.start()
    release = asyncio.Event()

    async def blocking() -> None:
        await release.wait()

    scheduler.submit(key="running", job=blocking)
    await _settle()
    assert scheduler.submit(key="queued", job=blocking) is True

    with caplog.at_level(logging.WARNING):
        assert scheduler.submit(key="dropped", job=blocking) is False
    assert "Background queue is full" in caplog.text

    release.set()
    await scheduler.stop()


@pytest.mark.asyncio
async def test_shutdown_cancels_work_in_flight_instead_of_waiting_for_it() -> None:
    """Draining would hold a restart on a model call the next turn redoes anyway."""
    scheduler = AsyncioTaskScheduler()
    await scheduler.start()
    started = asyncio.Event()
    finished = False

    async def slow() -> None:
        nonlocal finished
        started.set()
        await asyncio.sleep(30)
        finished = True

    scheduler.submit(key="memory:1", job=slow)
    await asyncio.wait_for(started.wait(), timeout=1)

    await asyncio.wait_for(scheduler.stop(), timeout=1)

    assert finished is False


@pytest.mark.asyncio
async def test_submitting_before_the_worker_runs_is_refused_rather_than_lost_silently() -> None:
    scheduler = AsyncioTaskScheduler()

    async def job() -> None:
        return None

    assert scheduler.submit(key="memory:1", job=job) is False
