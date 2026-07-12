from dataclasses import dataclass, field

from rp_engine.core.conversation.role import ConversationRole


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: ConversationRole
    content: str
    metadata: dict[str, str] = field(default_factory=dict)