from typing import Protocol

from rp_engine.core.engine.models import PromptPayload


class LLMProvider(Protocol):
    async def generate_response(self, prompt: PromptPayload) -> str: ...
