import logging

from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.ports import LLMProvider

logger = logging.getLogger(__name__)

class RPOrchestrator:
    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def generate_reply(self, request: GenerationRequest) -> str:
        logger.info("Orchestrator started", extra={"memory_key": request.memory_key.value})
        response = await self._llm_provider.generate_response(request.conversation)
        logger.info("Response generated", extra={"memory_key": request.memory_key.value})
        return response
