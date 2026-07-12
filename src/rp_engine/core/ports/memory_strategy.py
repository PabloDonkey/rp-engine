from typing import Protocol

from rp_engine.core.conversation.message import ConversationMessage


class MemoryStrategy(Protocol):
    def build_context(self, messages: list[ConversationMessage]) -> list[ConversationMessage]: ...
