"""Layer 00 — the recent window.

The conversation itself, cut to what the budget can hold. It stores nothing of its own and
observes nothing: it reads the messages the pipeline hands it and keeps the newest ones
that fit.

It replaces `DumpEverythingStrategy`, which returned every message ever stored. The only
real change is that it stops at a budget.
"""

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.fragment import PRIORITY_RECENT_WINDOW, MemoryFragment
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecallContext
from rp_engine.core.ports.memory_source import MemorySource
from rp_engine.core.ports.token_counter import TokenCounter

# Tokens charged for a message on top of its text: every chat format wraps a message in a
# role marker and a separator or two. Four is a deliberate over-estimate, because
# over-counting drops a message that would have fit while under-counting overflows the
# window and loses the turn.
MESSAGE_OVERHEAD_TOKENS = 4


class RecentWindowSource(MemorySource):
    id = "recent_window"

    def __init__(self, *, token_counter: TokenCounter) -> None:
        self._token_counter = token_counter

    async def recall(self, context: MemoryRecallContext) -> tuple[MemoryFragment, ...]:
        """Keep the newest turns that fit, oldest first in the result.

        Whole messages only. Half a message is a sentence that stops in the middle of a
        scene, which reads to the model as text it should continue rather than context it
        should use.

        A message that alone exceeds the whole budget stops the walk instead of being
        skipped: skipping it would put the turns *around* a missing turn into the prompt,
        which reads as a story with a hole in it rather than a story that starts later.
        """
        if context.remaining_budget <= 0 or not context.recent_messages:
            return ()

        kept: list[ConversationMessage] = []
        used = 0
        for message in reversed(context.recent_messages):
            cost = await self._cost(message)
            if used + cost > context.remaining_budget:
                break
            kept.append(message)
            used += cost

        if not kept:
            return ()
        kept.reverse()
        return (
            MemoryFragment(
                source="recent_window",
                label="[Recent Conversation]",
                body="",
                priority=PRIORITY_RECENT_WINDOW,
                tokens=used,
                messages=tuple(kept),
            ),
        )

    async def observe(self, context: MemoryObserveContext) -> None:
        """Nothing to do. The conversation store already recorded the turn."""
        return None

    async def _cost(self, message: ConversationMessage) -> int:
        return await self._token_counter.count_tokens(message.content) + MESSAGE_OVERHEAD_TOKENS
