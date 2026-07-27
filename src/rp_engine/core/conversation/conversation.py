from dataclasses import dataclass, field

from rp_engine.core.conversation.message import ConversationMessage


@dataclass(frozen=True, slots=True)
class Conversation:
    messages: list[ConversationMessage]
    metadata: dict[str, str] = field(default_factory=dict)
    # When set, the final message is a *prefix to continue*, not a completed turn: the
    # provider should keep generating from those exact tokens instead of opening a new
    # assistant turn. Opening a new turn is what makes a reasoning model re-plan from
    # scratch, which is how a resume can burn its whole budget thinking and return no prose.
    # Providers that cannot prefill may ignore this and fall back to an instruction turn.
    continue_final_message: bool = False