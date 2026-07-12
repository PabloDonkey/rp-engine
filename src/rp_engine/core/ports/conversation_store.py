from typing import Protocol

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import MemoryKey


class ConversationStore(Protocol):
    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None: ...

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]: ...

    async def clear(self, memory_key: MemoryKey) -> None: ...
