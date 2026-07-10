import logging

from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, orchestrator: RPOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def handle_user_message(self, *, user_id: str, message: str) -> str:
        logger.info("ChatService called", extra={"user_id": user_id})
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("Message must not be empty.")

        request = GenerationRequest(user_id=user_id, message=cleaned_message)
        return await self._orchestrator.generate_reply(request)
