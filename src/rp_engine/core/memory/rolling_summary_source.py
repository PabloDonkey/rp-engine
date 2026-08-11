"""Layer 01 — the rolling summary.

Layer 00 keeps a budgeted window, so everything older than the window is simply gone. This
layer catches it: what falls out of the window is condensed into one running recap, and the
recap is condensed again when it outgrows its own budget.

`recall` is one indexed read and costs the turn nothing. `observe` runs in the background
worker, asks "is this session's recap behind?", and re-reads everything it needs from
storage — it is never told what to summarize (ADR-026 decision 1).

It is lossy by construction. A recap can say that a duel happened; it cannot give back the
exact line someone swore. Layers 02 and 04 exist for that, so do not close the gap here by
making recaps longer.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.fragment import PRIORITY_ROLLING_SUMMARY, MemoryFragment
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecallContext
from rp_engine.core.memory.recent_window_source import MESSAGE_OVERHEAD_TOKENS
from rp_engine.core.memory.session_summary import SessionSummary
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.conversation_summarizer import ConversationSummarizer
from rp_engine.core.ports.memory_source import MemorySource
from rp_engine.core.ports.session_summary_store import SessionSummaryStore
from rp_engine.core.ports.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# The label the recap carries into the memory section of the prompt.
STORY_SO_FAR_LABEL = "[Story So Far]"

# Where the recap catches up: at this share of the window budget, not at the budget
# (ADR-026 decision 1, rule 5). Summarizing while the window still has room is what keeps
# the window from ever having to drop a message the recap does not yet cover, and it turns
# an overflow into an alarm rather than the routine case.
DEFAULT_HIGH_WATER_SHARE = 0.75

# Words asked of the summarizer per token of budget. English runs near 0.75 words per
# token; asking for less leaves room for the recap to overshoot without being dropped.
WORDS_PER_TOKEN = 0.6
# The recap stays short on purpose: recent, clearly stated detail beats a long buried one.
MIN_TARGET_WORDS = 50
MAX_TARGET_WORDS = 250


@dataclass(frozen=True, slots=True)
class _WindowMarks:
    """Where the stored messages sit against the budget, counted newest first.

    Both are indices into the message list, and both name a prefix: `messages[:index]` is
    the part on the far side of that mark.
    """

    # Outside the high-water mark. This is what the next pass folds into the recap.
    high_water_index: int
    # Outside the window budget altogether. The window cannot replay these at all, so a
    # recap that does not reach this far has already lost story.
    window_index: int


class RollingSummarySource(MemorySource):
    id = "rolling_summary"

    def __init__(
        self,
        *,
        summary_store: SessionSummaryStore,
        conversation_store: ConversationStore,
        summarizer: ConversationSummarizer,
        token_counter: TokenCounter,
        model_name: str,
        high_water_share: float = DEFAULT_HIGH_WATER_SHARE,
    ) -> None:
        if not 0.0 < high_water_share <= 1.0:
            raise ValueError("high_water_share must be greater than 0 and at most 1.")
        self._summary_store = summary_store
        self._conversation_store = conversation_store
        self._summarizer = summarizer
        self._token_counter = token_counter
        self._model_name = model_name
        self._high_water_share = high_water_share

    async def recall(self, context: MemoryRecallContext) -> tuple[MemoryFragment, ...]:
        """Return the stored recap, or nothing when there is none yet.

        The recap is returned even when it costs more than this layer's share of the
        budget. Reporting the real cost and letting the pipeline drop the fragment is the
        contract (ADR-026 rule 3); trimming the text here would hand the model a recap that
        stops mid-sentence.
        """
        stored = await self._summary_store.get(context.session_id)
        if stored is None or not stored.summary.strip():
            return ()
        return (
            MemoryFragment(
                source="rolling_summary",
                label=STORY_SO_FAR_LABEL,
                body=stored.summary,
                priority=PRIORITY_ROLLING_SUMMARY,
                tokens=stored.tokens,
            ),
        )

    async def observe(self, context: MemoryObserveContext) -> None:
        """Catch the recap up with the story, if it is behind.

        Everything it needs is re-read here: the job that got it running carried only the
        session id and the turn, so running it late, twice, or not at all all end in the
        same stored state.
        """
        if context.memory_budget <= 0:
            return
        memory_key = ConversationIdentity.for_session(str(context.session_id)).to_memory_key()
        messages = await self._conversation_store.load_messages(memory_key)
        if not messages:
            return

        stored = await self._summary_store.get(context.session_id)
        covered_turn = stored.covers_through_turn if stored is not None else 0
        marks = await self._window_marks(messages, context.memory_budget)
        # Checked before the pass, not after: the question is what the *turn that just
        # ran* could carry. This pass is about to close the gap, which is exactly why it
        # would be invisible if it were measured afterwards.
        self._warn_if_behind(
            context=context, messages=messages, marks=marks, covered=covered_turn
        )
        fold_through = self._end_of_turn(messages, marks.high_water_index)
        pending = messages[self._index_after_turn(messages, covered_turn) : fold_through]
        pending_turn = self._turns_before(messages, fold_through)

        summary = stored.summary if stored is not None else ""
        tokens = stored.tokens if stored is not None else 0
        covers_through_turn = covered_turn
        if pending and pending_turn > covered_turn:
            summary = await self._summarizer.summarize_story_so_far(
                previous_summary=summary,
                new_messages=list(pending),
                target_words=self._target_words(context.source_budget),
            )
            if not summary.strip():
                logger.warning(
                    "The summarizer returned nothing for session %s; the recap is unchanged.",
                    context.session_id,
                    extra={"session_id": str(context.session_id), "turn": context.turn},
                )
                return
            covers_through_turn = pending_turn
            tokens = await self._token_counter.count_tokens(summary)

        summary, tokens = await self._condensed_to_budget(
            summary=summary,
            tokens=tokens,
            budget=context.source_budget,
            session_id=str(context.session_id),
        )
        unchanged = (
            stored is not None
            and stored.summary == summary
            and stored.covers_through_turn == covers_through_turn
            and stored.model_name == self._model_name
        )
        if unchanged or not summary.strip():
            return

        await self._summary_store.save(
            stored.rewritten(
                summary=summary,
                covers_through_turn=covers_through_turn,
                tokens=tokens,
                model_name=self._model_name,
            )
            if stored is not None
            else SessionSummary.create(
                session_id=context.session_id,
                summary=summary,
                covers_through_turn=covers_through_turn,
                tokens=tokens,
                model_name=self._model_name,
            )
        )
        logger.info(
            "Rolling summary updated through turn %d (%d tokens).",
            covers_through_turn,
            tokens,
            extra={
                "session_id": str(context.session_id),
                "covers_through_turn": covers_through_turn,
                "summary_tokens": tokens,
            },
        )

    async def _condensed_to_budget(
        self,
        *,
        summary: str,
        tokens: int,
        budget: int,
        session_id: str,
    ) -> tuple[str, int]:
        """Summarize the summary when it has outgrown its own budget.

        One pass only. A recap that is still too long after being condensed is reported by
        the pipeline dropping it, which is a fact worth seeing; a loop that keeps calling
        the model until a number comes down is not.
        """
        if budget <= 0 or tokens <= budget or not summary.strip():
            return summary, tokens
        condensed = await self._summarizer.condense_story_summary(
            summary=summary,
            target_words=self._target_words(budget),
        )
        if not condensed.strip():
            return summary, tokens
        condensed_tokens = await self._token_counter.count_tokens(condensed)
        logger.info(
            "Rolling summary re-condensed from %d to %d tokens against a budget of %d.",
            tokens,
            condensed_tokens,
            budget,
            extra={"session_id": session_id, "summary_tokens": condensed_tokens},
        )
        return condensed, condensed_tokens

    def _warn_if_behind(
        self,
        *,
        context: MemoryObserveContext,
        messages: Sequence[ConversationMessage],
        marks: _WindowMarks,
        covered: int,
    ) -> None:
        """The one memory warning ADR-026 asks for.

        Messages outside the window budget were gone from the prompt this turn. With this
        layer on, the recap should already have covered them, because it catches up at the
        high-water mark below the budget. If it had not, story left the prompt with nothing
        speaking for it, and that is an alarm rather than the routine drop layer 00 never
        logs.

        It fires on the turn *after* the loss, which is as early as anything can see it,
        and the same pass then closes the gap.
        """
        uncovered = self._turns_before(messages, marks.window_index) - covered
        if uncovered <= 0:
            return
        logger.warning(
            "The rolling summary is behind: %d turn(s) fell outside the window before the "
            "recap covered them.",
            uncovered,
            extra={
                "session_id": str(context.session_id),
                "covers_through_turn": covered,
                "uncovered_turns": uncovered,
            },
        )

    async def _window_marks(
        self, messages: Sequence[ConversationMessage], memory_budget: int
    ) -> _WindowMarks:
        """Walk newest to oldest once, marking the high-water line and the window edge.

        The walk stops at the window edge, so it costs one token count per message the
        window can hold rather than one per message ever stored — and those are the same
        counts layer 00 asks for on the turn path, so they come from the cache.
        """
        high_water_tokens = int(memory_budget * self._high_water_share)
        high_water_index = len(messages)
        window_index = len(messages)
        used = 0
        for position in range(len(messages) - 1, -1, -1):
            cost = await self._cost(messages[position])
            if used + cost > memory_budget:
                break
            used += cost
            window_index = position
            if used <= high_water_tokens:
                high_water_index = position
        return _WindowMarks(high_water_index=high_water_index, window_index=window_index)

    async def _cost(self, message: ConversationMessage) -> int:
        return await self._token_counter.count_tokens(message.content) + MESSAGE_OVERHEAD_TOKENS

    @staticmethod
    def _target_words(budget: int) -> int:
        return max(MIN_TARGET_WORDS, min(MAX_TARGET_WORDS, int(budget * WORDS_PER_TOKEN)))

    @staticmethod
    def _end_of_turn(messages: Sequence[ConversationMessage], boundary: int) -> int:
        """Pull a fold boundary back to just after a narrator reply.

        A turn is a player message and the reply to it. Folding half of one would put the
        player's line in the recap and leave the answer to it in the window, which reads as
        the story answering something it was never asked.
        """
        while boundary > 0 and messages[boundary - 1].role != ConversationRole.CHARACTER:
            boundary -= 1
        return boundary

    @staticmethod
    def _turns_before(messages: Sequence[ConversationMessage], boundary: int) -> int:
        return sum(
            1 for message in messages[:boundary] if message.role == ConversationRole.CHARACTER
        )

    @staticmethod
    def _index_after_turn(messages: Sequence[ConversationMessage], turn: int) -> int:
        """Where the recap stopped last time, as an index into the stored messages."""
        if turn <= 0:
            return 0
        seen = 0
        for index, message in enumerate(messages):
            if message.role != ConversationRole.CHARACTER:
                continue
            seen += 1
            if seen == turn:
                return index + 1
        return len(messages)
