from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.ports.memory_strategy import MemoryStrategy


class DumpEverythingStrategy(MemoryStrategy):
    def build_context(self, messages: list[ConversationMessage]) -> list[ConversationMessage]:
        return list(messages)
