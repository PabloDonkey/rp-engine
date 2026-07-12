from typing import Protocol

from rp_engine.core.conversation.conversation import Conversation


class LLMProvider(Protocol):
    async def generate_response(self, conversation: Conversation) -> str: ...
