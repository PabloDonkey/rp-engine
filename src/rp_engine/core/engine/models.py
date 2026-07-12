from dataclasses import dataclass

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.memory.models import MemoryKey


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    memory_key: MemoryKey
    conversation: Conversation
    settings: GenerationSettings
