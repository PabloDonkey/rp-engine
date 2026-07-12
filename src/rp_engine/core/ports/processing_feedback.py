import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeedbackContext:
    conversation_owner_id: str
    character_id: str
    character_name: str
    user_display_name: str
    world_id: str


class ProcessingFeedback(Protocol):
    async def start(self, context: FeedbackContext) -> None: ...

    async def update(self, message: str) -> None: ...

    async def stop(self) -> None: ...


class NoOpProcessingFeedback:
    async def start(self, context: FeedbackContext) -> None:
        del context

    async def update(self, message: str) -> None:
        del message

    async def stop(self) -> None:
        return None


@asynccontextmanager
async def processing_feedback_scope(
    feedback: ProcessingFeedback,
    *,
    context: FeedbackContext,
) -> AsyncIterator[None]:
    started = False
    try:
        await feedback.start(context)
        started = True
    except Exception:
        logger.exception("Failed to start processing feedback")

    try:
        yield
    finally:
        if started:
            try:
                await feedback.stop()
            except Exception:
                logger.exception("Failed to stop processing feedback")
