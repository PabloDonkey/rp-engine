from dataclasses import dataclass, field

from rp_engine.core.conversation.role import ConversationRole

# Conversation-message metadata keys. These are domain vocabulary, not one service's private
# detail: infrastructure reads `finish_reason` too (a reply that stopped at `length` is a
# fragment of the next one, not a separate beat), so they live in the core where both the
# application and infrastructure layers may depend on them.
#
# Records why generation stopped for a narrator turn.
FINISH_REASON_METADATA_KEY = "finish_reason"
# finish_reason value meaning the model hit its token limit mid-reply.
FINISH_REASON_LENGTH = "length"
# Records the character-reply turn number.
TURN_METADATA_KEY = "turn"
# Records the model's captured thinking/reasoning text.
THINKING_METADATA_KEY = "thinking"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: ConversationRole
    content: str
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def was_truncated(self) -> bool:
        """Whether this reply stopped at the token limit, i.e. it is unfinished text."""
        return self.metadata.get(FINISH_REASON_METADATA_KEY) == FINISH_REASON_LENGTH