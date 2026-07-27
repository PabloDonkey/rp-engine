from typing import Protocol

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import MemoryKey


class ConversationStore(Protocol):
    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None: ...

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]: ...

    async def clear(self, memory_key: MemoryKey) -> None: ...

    async def delete_last_message(
        self, memory_key: MemoryKey
    ) -> ConversationMessage | None:
        """Remove the newest message, returning it, or None when there is nothing to remove.

        Deliberately last-only: a conversation is an ordered narrative, and removing from the
        middle would leave replies answering messages that no longer exist. Undoing a bad turn
        therefore means peeling from the end, which is also what makes it safe — the model
        never sees a history that could not have happened.
        """
        ...
