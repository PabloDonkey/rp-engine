import logging

from rp_engine.core.engine.models import GenerationRequest, PromptPayload
from rp_engine.core.memory.models import ConversationMessage
from rp_engine.core.ports import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are RP Engine, a collaborative roleplay assistant. "
    "Generate concise, immersive responses that continue the scene."
)


class RPOrchestrator:
    def __init__(
        self,
        llm_provider: LLMProvider,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._llm_provider = llm_provider
        self._system_prompt = system_prompt

    async def generate_reply(self, request: GenerationRequest) -> str:
        logger.info("Orchestrator started", extra={"memory_key": request.memory_key.value})
        prompt = self._build_prompt(request)
        response = await self._llm_provider.generate_response(prompt)
        logger.info("Response generated", extra={"memory_key": request.memory_key.value})
        return response

    def _build_prompt(self, request: GenerationRequest) -> PromptPayload:
        if not request.context_messages:
            return PromptPayload(
                system_prompt=self._system_prompt,
                user_message=request.instruction,
            )

        history = self._format_history(request.context_messages)
        user_message = f"Conversation history:\n{history}\n\nNext input:\n{request.instruction}"
        return PromptPayload(system_prompt=self._system_prompt, user_message=user_message)

    @staticmethod
    def _format_history(messages: list[ConversationMessage]) -> str:
        lines: list[str] = []
        for message in messages:
            speaker = "User" if message.role == "user" else "Assistant"
            lines.append(f"{speaker}: {message.content}")
        return "\n".join(lines)
