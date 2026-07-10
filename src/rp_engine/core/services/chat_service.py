from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator


class ChatService:
    def __init__(self, orchestrator: RPOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def handle_user_message(self, *, user_id: str, message: str) -> str:
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("Message must not be empty.")

        request = GenerationRequest(user_id=user_id, message=cleaned_message)
        return await self._orchestrator.generate_reply(request)
