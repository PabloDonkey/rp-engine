from dataclasses import dataclass

from rp_engine.core.memory.models import ConversationMessage, MemoryKey


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    memory_key: MemoryKey
    context_messages: list[ConversationMessage]
    instruction: str


@dataclass(frozen=True, slots=True)
class PromptPayload:
    system_prompt: str
    user_message: str
