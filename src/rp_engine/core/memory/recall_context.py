"""What a memory layer is allowed to see, and what the pipeline gives back.

Two narrow read models, not one, and never the live `ScenarioSession` (ADR-026). Whatever
a source can read becomes a contract that is hard to change once five layers depend on it,
so each type carries the least that its half of the port needs.
"""

from dataclasses import dataclass
from uuid import UUID

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.fragment import MemoryFragment


@dataclass(frozen=True, slots=True)
class MemoryRecallContext:
    """The read half's input. Built fresh for every turn, on the turn path."""

    session_id: UUID
    scenario_definition_id: str
    # The stored conversation, oldest first. Layer 00 cuts its window from this; the later
    # layers read the tail of it to decide what to look up.
    recent_messages: tuple[ConversationMessage, ...]
    # What the player just sent, before it is stored.
    current_user_message: str
    # How many tokens this source may spend. The pipeline works it out and hands it over;
    # a source never reads the budget from anywhere else.
    remaining_budget: int


@dataclass(frozen=True, slots=True)
class MemoryObserveContext:
    """The write half's input.

    It runs in the background worker, seconds after the turn, so it carries identifiers
    only. Carrying the message text would make the job a command carrying data, and
    ADR-026 requires a job to be a question about stored state — that is what makes a job
    lost to a restart harmless.
    """

    session_id: UUID
    scenario_definition_id: str
    turn: int


@dataclass(frozen=True, slots=True)
class MemoryRecall:
    """What the pipeline recalled for one turn, after the budget was applied.

    The two halves land in different places in the prompt: `messages` are replayed as chat
    turns, `fragments` render into the memory section of the system prompt.
    """

    messages: tuple[ConversationMessage, ...] = ()
    fragments: tuple[MemoryFragment, ...] = ()
    budget_tokens: int = 0
    used_tokens: int = 0
    # What the budget could not hold. It goes into the generation trace record and nowhere
    # else (ADR-026): with layer 01 off this happens on every turn of every long session,
    # and a warning that always fires is a warning nobody reads.
    #
    # How many stored turns did not reach the prompt. Their token total is deliberately
    # not reported: the window stops counting at the first message that does not fit, so a
    # total would mean counting the whole history on every turn — the exact cost the walk
    # exists to avoid. The count is the number that says story left the prompt.
    dropped_messages: int = 0
    # Tokens in whole fragments the budget dropped, from layers 01 to 04.
    dropped_fragment_tokens: int = 0

    def to_trace_record(self) -> dict[str, int]:
        """The shape the generation trace stores under its `memory` key."""
        return {
            "budget_tokens": self.budget_tokens,
            "used_tokens": self.used_tokens,
            "dropped_messages": self.dropped_messages,
            "dropped_fragment_tokens": self.dropped_fragment_tokens,
        }
