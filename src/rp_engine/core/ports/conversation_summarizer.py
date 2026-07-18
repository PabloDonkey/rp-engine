from typing import Protocol

from rp_engine.core.conversation.message import ConversationMessage


class ConversationSummarizer(Protocol):
    async def summarize_recent_conversation(
        self,
        *,
        recent_messages: list[ConversationMessage],
    ) -> str: ...