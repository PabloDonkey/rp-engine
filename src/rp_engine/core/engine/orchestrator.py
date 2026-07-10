from rp_engine.core.engine.llm_provider import LLMProvider
from rp_engine.core.engine.models import GenerationRequest, PromptPayload

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
        prompt = self._build_prompt(request)
        return await self._llm_provider.generate_response(prompt)

    def _build_prompt(self, request: GenerationRequest) -> PromptPayload:
        return PromptPayload(system_prompt=self._system_prompt, user_message=request.message)
