from dataclasses import dataclass, field

from rp_engine.core.conversation.message import ConversationMessage


@dataclass(frozen=True, slots=True)
class Conversation:
    messages: list[ConversationMessage]
    metadata: dict[str, str] = field(default_factory=dict)