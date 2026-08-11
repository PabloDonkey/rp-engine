"""What a memory layer hands back, and how much of the prompt it costs.

One value type for all five layers (ADR-026). A layer never writes to the prompt and never
decides whether it fits: it returns fragments with a stated cost, and `MemoryPipeline`
decides what the budget can hold.
"""

from dataclasses import dataclass
from typing import Literal

from rp_engine.core.conversation.message import ConversationMessage

# The five layers of ADR-026. Layer 00 is the recent window; the rest arrive in S023 to
# S026 and are switched per session.
MemorySystemId = Literal[
    "recent_window",
    "rolling_summary",
    "lorebook",
    "fact_state",
    "semantic_recall",
]

# The layers a session may switch off. Layer 00 is missing on purpose: it is the
# conversation itself, so "recent window disabled" must not be expressible (ADR-026
# implementation rule 5). Leaving it out of this type makes that a type error rather than
# a check someone has to remember to run.
ToggleableMemorySystemId = Literal[
    "rolling_summary",
    "lorebook",
    "fact_state",
    "semantic_recall",
]

# Priorities decide who survives budget contention: the higher the number, the later a
# fragment is dropped. The recent window sits above every other layer because it is the
# conversation, and a prompt without it has no scene to continue.
PRIORITY_RECENT_WINDOW = 100


@dataclass(frozen=True, slots=True)
class MemoryFragment:
    """One block of recalled context, with the price it charges to the budget.

    `messages` is the exception the recent window needs. Layers 01 to 04 recall *text*,
    which renders into the memory section of the system prompt. Layer 00 recalls the
    conversation itself, which has to reach the model as chat turns with their own roles —
    flattening it into text would undo the assistant-role mapping (S017) and the prefill
    continuation that depends on it (S018). Such a fragment carries its turns here and
    leaves `body` empty; everything else about it, including how the budget treats it, is
    the same as any other fragment.
    """

    source: MemorySystemId
    label: str
    body: str
    priority: int
    tokens: int
    messages: tuple[ConversationMessage, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.body.strip() and not self.messages
