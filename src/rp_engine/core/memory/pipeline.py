"""The composite that runs the memory layers and spends the budget.

`MemoryPipeline` is the only thing that decides what fits. A source reports what its
fragments cost; the pipeline drops whole fragments, lowest priority first, until the block
fits the room the prompt has left (ADR-026).
"""

import asyncio
import logging
from collections.abc import Sequence
from uuid import UUID

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.context_budget import ContextBudget
from rp_engine.core.memory.fragment import MemoryFragment
from rp_engine.core.memory.recall_context import (
    MemoryObserveContext,
    MemoryRecall,
    MemoryRecallContext,
)
from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.ports.memory_source import MemorySource

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """Runs the enabled sources, merges what they recalled, and cuts it to the budget."""

    def __init__(
        self,
        *,
        sources: Sequence[MemorySource],
        context_budget: ContextBudget,
    ) -> None:
        self._sources = tuple(sources)
        self._context_budget = context_budget

    async def recall(
        self,
        *,
        session_id: UUID,
        scenario_definition_id: str,
        messages: Sequence[ConversationMessage],
        current_user_message: str,
        reserved_tokens: int,
        settings: MemorySettings,
    ) -> MemoryRecall:
        """Recall context for one turn.

        `reserved_tokens` is what the rest of the prompt already costs — the system
        sections and the message the player just sent. Memory gets what is left of the
        budget, so a long character card or a stack of session rules takes room from the
        window rather than pushing the prompt past the window.
        """
        total = await self._context_budget.total_tokens()
        available = max(0, total - reserved_tokens)
        if available <= 0:
            # Not the routine case ADR-026 keeps out of the log. Routine is "an old turn
            # left the prompt". This is "the character card and the rules alone fill the
            # window", which leaves the model with no story at all and repeats on every
            # turn of that scenario until someone shortens it or loads a bigger model.
            logger.warning(
                "The prompt has no room left for memory: %d tokens of budget, %d already "
                "spent on the other sections.",
                total,
                reserved_tokens,
                extra={"session_id": str(session_id), "reserved_tokens": reserved_tokens},
            )
        enabled = [source for source in self._sources if settings.is_enabled(source.id)]
        if not enabled or available <= 0:
            return MemoryRecall(budget_tokens=available, dropped_messages=len(messages))

        context = MemoryRecallContext(
            session_id=session_id,
            scenario_definition_id=scenario_definition_id,
            recent_messages=tuple(messages),
            current_user_message=current_user_message,
            remaining_budget=available,
        )
        # Every source is offered the whole budget and they run at the same time, so the
        # sum of what they return can exceed it. That is what the cut below is for: the
        # alternative, handing out fixed shares up front, wastes the share of any source
        # that had nothing to say this turn.
        results = await asyncio.gather(
            *(source.recall(context) for source in enabled),
            return_exceptions=True,
        )

        recalled: list[MemoryFragment] = []
        for source, result in zip(enabled, results, strict=True):
            if isinstance(result, BaseException):
                # Implementation rule 4: a broken layer costs its own context, never the
                # turn. The player gets a reply with less memory rather than an error.
                logger.warning(
                    "Memory source %s failed to recall; continuing without it.",
                    source.id,
                    exc_info=result,
                    extra={"session_id": str(session_id), "memory_source": source.id},
                )
                continue
            recalled.extend(fragment for fragment in result if not fragment.is_empty)

        return self._apply_budget(
            fragments=recalled,
            available=available,
            stored_message_count=len(messages),
        )

    async def observe(self, context: MemoryObserveContext, *, settings: MemorySettings) -> None:
        """Tell the enabled sources that a turn completed.

        Runs off the turn path, in the background worker S023 introduces. Failures are
        logged and swallowed for the same reason `recall` swallows them: nothing here is
        allowed to reach the player.
        """
        enabled = [source for source in self._sources if settings.is_enabled(source.id)]
        results = await asyncio.gather(
            *(source.observe(context) for source in enabled),
            return_exceptions=True,
        )
        for source, result in zip(enabled, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    "Memory source %s failed to observe turn %d.",
                    source.id,
                    context.turn,
                    exc_info=result,
                    extra={"session_id": str(context.session_id), "memory_source": source.id},
                )

    @staticmethod
    def _apply_budget(
        *,
        fragments: Sequence[MemoryFragment],
        available: int,
        stored_message_count: int,
    ) -> MemoryRecall:
        """Keep the most important fragments that fit, in priority order.

        Fragments are dropped whole. A fragment is a layer's answer, and half an answer —
        a summary that stops mid-sentence, a lore entry missing its second half — is worse
        than not asking that layer at all. The recent window trimmed itself to the budget
        already, and it outranks every other layer, so it is never the one dropped.
        """
        ordered = sorted(fragments, key=lambda fragment: -fragment.priority)
        kept: list[MemoryFragment] = []
        used = 0
        dropped_fragment_tokens = 0
        for fragment in ordered:
            if used + fragment.tokens > available:
                dropped_fragment_tokens += fragment.tokens
                continue
            kept.append(fragment)
            used += fragment.tokens

        replayed = tuple(message for fragment in kept for message in fragment.messages)
        return MemoryRecall(
            messages=replayed,
            fragments=tuple(fragment for fragment in kept if fragment.body.strip()),
            budget_tokens=available,
            used_tokens=used,
            dropped_messages=max(0, stored_message_count - len(replayed)),
            dropped_fragment_tokens=dropped_fragment_tokens,
        )
