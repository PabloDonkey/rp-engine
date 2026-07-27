from typing import Protocol

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse


class LLMProvider(Protocol):
    async def generate(
        self,
        conversation: Conversation,
        settings: GenerationSettings,
    ) -> LLMResponse:
        """Generate one reply for `conversation`.

        When `conversation.continue_final_message` is set, the final message is a **prefix
        to continue**, not a completed turn: keep generating from those exact tokens rather
        than opening a new assistant turn. A provider that cannot express prefill may ignore
        the flag and treat it as an ordinary request — the reply is then a fresh turn rather
        than a continuation, which is a degradation, not a failure.
        """
        ...
