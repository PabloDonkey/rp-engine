from typing import Protocol

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse


class LLMProvider(Protocol):
    async def generate(
        self,
        conversation: Conversation,
        settings: GenerationSettings,
    ) -> LLMResponse: ...
