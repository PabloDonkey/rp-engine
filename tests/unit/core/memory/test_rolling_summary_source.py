import logging
from collections.abc import Sequence
from uuid import UUID

import pytest

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.fragment import PRIORITY_ROLLING_SUMMARY
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecallContext
from rp_engine.core.memory.rolling_summary_source import (
    STORY_SO_FAR_LABEL,
    RollingSummarySource,
)
from rp_engine.core.memory.session_summary import SessionSummary

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")
DEFINITION_ID = "scenario-1"
MODEL_NAME = "test-model"

# Every message in these tests is one word long, so it costs one token plus the four-token
# per-message overhead the window charges: five tokens each, which makes the budget
# arithmetic below something a reader can check by hand.
TOKENS_PER_MESSAGE = 5


class WordTokenCounter:
    async def count_tokens(self, text: str) -> int:
        return len(text.split())


class FakeSummaryStore:
    def __init__(self, stored: SessionSummary | None = None) -> None:
        self.stored = stored
        self.saves = 0

    async def get(self, session_id: UUID) -> SessionSummary | None:
        return self.stored

    async def save(self, summary: SessionSummary) -> SessionSummary:
        self.stored = summary
        self.saves += 1
        return summary


class FakeConversationStore:
    def __init__(self, messages: Sequence[ConversationMessage]) -> None:
        self._messages = list(messages)

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        raise NotImplementedError

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self._messages)

    async def clear(self, memory_key: MemoryKey) -> None:
        raise NotImplementedError

    async def delete_last_message(self, memory_key: MemoryKey) -> ConversationMessage | None:
        raise NotImplementedError


class FakeSummarizer:
    """Records what it was asked to summarize and returns what the test tells it to."""

    def __init__(self, *, summary: str = "the recap", condensed: str = "short") -> None:
        self._summary = summary
        self._condensed = condensed
        self.folded: list[tuple[str, tuple[str, ...]]] = []
        self.condensed_from: list[str] = []

    async def summarize_story_so_far(
        self,
        *,
        previous_summary: str,
        new_messages: Sequence[ConversationMessage],
        target_words: int,
    ) -> str:
        self.folded.append(
            (previous_summary, tuple(message.content for message in new_messages))
        )
        return self._summary

    async def condense_story_summary(self, *, summary: str, target_words: int) -> str:
        self.condensed_from.append(summary)
        return self._condensed


def _messages(count: int) -> list[ConversationMessage]:
    """Alternating player and narrator turns: even index is the player, odd the story."""
    return [
        ConversationMessage(
            role=ConversationRole.USER if index % 2 == 0 else ConversationRole.CHARACTER,
            content=f"m{index}",
        )
        for index in range(count)
    ]


def _source(
    *,
    messages: Sequence[ConversationMessage],
    summary_store: FakeSummaryStore,
    summarizer: FakeSummarizer,
) -> RollingSummarySource:
    return RollingSummarySource(
        summary_store=summary_store,
        conversation_store=FakeConversationStore(messages),
        summarizer=summarizer,
        token_counter=WordTokenCounter(),
        model_name=MODEL_NAME,
    )


def _observe_context(*, turn: int, memory_budget: int, source_budget: int) -> MemoryObserveContext:
    return MemoryObserveContext(
        session_id=SESSION_ID,
        scenario_definition_id=DEFINITION_ID,
        turn=turn,
        memory_budget=memory_budget,
        source_budget=source_budget,
    )


def _stored(summary: str = "earlier recap", *, turn: int, tokens: int = 2) -> SessionSummary:
    return SessionSummary.create(
        session_id=SESSION_ID,
        summary=summary,
        covers_through_turn=turn,
        tokens=tokens,
        model_name=MODEL_NAME,
    )


@pytest.mark.asyncio
async def test_recall_returns_the_stored_recap_as_one_fragment() -> None:
    store = FakeSummaryStore(_stored("They crossed the river.", turn=4, tokens=7))
    source = _source(messages=[], summary_store=store, summarizer=FakeSummarizer())

    fragments = await source.recall(
        MemoryRecallContext(
            session_id=SESSION_ID,
            scenario_definition_id=DEFINITION_ID,
            recent_messages=(),
            current_user_message="what now?",
            remaining_budget=100,
        )
    )

    assert len(fragments) == 1
    assert fragments[0].label == STORY_SO_FAR_LABEL
    assert fragments[0].body == "They crossed the river."
    assert fragments[0].tokens == 7
    assert fragments[0].priority == PRIORITY_ROLLING_SUMMARY
    # Layer 01 recalls text, not turns: replaying messages is layer 00's job.
    assert fragments[0].messages == ()


@pytest.mark.asyncio
async def test_recall_returns_nothing_before_the_first_recap_is_written() -> None:
    source = _source(messages=[], summary_store=FakeSummaryStore(), summarizer=FakeSummarizer())

    fragments = await source.recall(
        MemoryRecallContext(
            session_id=SESSION_ID,
            scenario_definition_id=DEFINITION_ID,
            recent_messages=(),
            current_user_message="hello",
            remaining_budget=100,
        )
    )

    assert fragments == ()


@pytest.mark.asyncio
async def test_a_story_inside_the_high_water_mark_is_not_summarized() -> None:
    # Ten messages cost 50 tokens, and the high-water mark is 75. Nothing has fallen far
    # enough behind to be worth a model call.
    store = FakeSummaryStore()
    summarizer = FakeSummarizer()
    source = _source(messages=_messages(10), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=5, memory_budget=100, source_budget=25))

    assert summarizer.folded == []
    assert store.saves == 0


@pytest.mark.asyncio
async def test_what_falls_past_the_high_water_mark_is_folded_into_a_recap() -> None:
    # 30 messages cost 150 tokens against a budget of 100, so the newest 15 fit under the
    # 75-token high-water mark and the oldest 15 do not.
    store = FakeSummaryStore()
    summarizer = FakeSummarizer(summary="They crossed the river.")
    messages = _messages(30)
    source = _source(messages=messages, summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    assert store.stored is not None
    assert store.stored.summary == "They crossed the river."
    assert store.stored.model_name == MODEL_NAME
    assert store.stored.tokens == 4
    previous, folded = summarizer.folded[0]
    assert previous == ""
    # The boundary stops after a narrator reply, so the fold covers whole turns.
    assert folded[-1] == "m13"
    assert store.stored.covers_through_turn == 7


@pytest.mark.asyncio
async def test_the_next_turn_does_not_summarize_the_same_stretch_again() -> None:
    store = FakeSummaryStore()
    summarizer = FakeSummarizer()
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))
    await source.observe(_observe_context(turn=16, memory_budget=100, source_budget=25))

    assert len(summarizer.folded) == 1
    assert store.saves == 1


@pytest.mark.asyncio
async def test_a_later_pass_folds_only_the_turns_the_recap_does_not_cover() -> None:
    store = FakeSummaryStore(_stored("They crossed the river.", turn=4))
    summarizer = FakeSummarizer()
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    previous, folded = summarizer.folded[0]
    # Turn 4 is the narrator reply at index 7, so the fold starts at the message after it.
    assert previous == "They crossed the river."
    assert folded[0] == "m8"
    assert folded[-1] == "m13"


@pytest.mark.asyncio
async def test_dropping_a_job_leaves_the_next_turn_writing_the_same_recap() -> None:
    """The property the whole background design rests on.

    A job lost to a restart costs nothing, because the job is a question about stored
    state: the next turn asks it again and reaches the same answer.
    """
    messages = _messages(30)

    ran_every_turn = FakeSummaryStore()
    source = _source(
        messages=messages, summary_store=ran_every_turn, summarizer=FakeSummarizer()
    )
    await source.observe(_observe_context(turn=14, memory_budget=100, source_budget=25))
    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    lost_the_first_job = FakeSummaryStore()
    recovered = _source(
        messages=messages, summary_store=lost_the_first_job, summarizer=FakeSummarizer()
    )
    await recovered.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    assert ran_every_turn.stored is not None
    assert lost_the_first_job.stored is not None
    assert ran_every_turn.stored.summary == lost_the_first_job.stored.summary
    assert (
        ran_every_turn.stored.covers_through_turn
        == lost_the_first_job.stored.covers_through_turn
    )


@pytest.mark.asyncio
async def test_a_recap_over_its_budget_is_condensed_and_stored_under_it() -> None:
    store = FakeSummaryStore()
    summarizer = FakeSummarizer(summary="one two three four five six", condensed="one two")
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=3))

    assert summarizer.condensed_from == ["one two three four five six"]
    assert store.stored is not None
    assert store.stored.summary == "one two"
    assert store.stored.tokens == 2
    assert store.stored.tokens <= 3


@pytest.mark.asyncio
async def test_a_stored_recap_that_outgrew_its_budget_is_condensed_with_no_new_turns() -> None:
    # Nothing new to fold — the budget itself shrank, which a smaller model does.
    store = FakeSummaryStore(_stored("one two three four", turn=7, tokens=4))
    summarizer = FakeSummarizer(condensed="one two")
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=2))

    assert summarizer.folded == []
    assert store.stored is not None
    assert store.stored.summary == "one two"
    assert store.stored.covers_through_turn == 7


@pytest.mark.asyncio
async def test_a_summarizer_that_returns_nothing_leaves_the_recap_alone() -> None:
    store = FakeSummaryStore(_stored("They crossed the river.", turn=4))
    summarizer = FakeSummarizer(summary="   ")
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    assert store.saves == 0
    assert store.stored is not None
    assert store.stored.summary == "They crossed the river."


@pytest.mark.asyncio
async def test_a_recap_behind_the_window_raises_the_one_memory_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ADR-026's alarm: story left the prompt with nothing speaking for it.

    The high-water mark exists so this never happens. Here the recap is pinned behind the
    window edge on purpose: at the turn that just ran, the window could hold turns 6 to 15
    and the recap only reached turn 1, so turns 2 to 5 reached the model through nothing at
    all. This pass then closes the gap.
    """
    store = FakeSummaryStore(_stored("They crossed the river.", turn=1))
    summarizer = FakeSummarizer(summary="They crossed the river and lost the map.")
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    with caplog.at_level(logging.WARNING):
        await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    assert "The rolling summary is behind" in caplog.text


@pytest.mark.asyncio
async def test_a_caught_up_recap_raises_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    # The window edge is turn 5 and the recap already reaches turn 7, which is what the
    # high-water mark is for.
    store = FakeSummaryStore(_stored(turn=7))
    source = _source(messages=_messages(30), summary_store=store, summarizer=FakeSummarizer())

    with caplog.at_level(logging.WARNING):
        await source.observe(_observe_context(turn=15, memory_budget=100, source_budget=25))

    assert "behind" not in caplog.text


@pytest.mark.asyncio
async def test_observe_does_nothing_without_a_budget() -> None:
    # A budget of zero means the prompt had no room at all, which the pipeline already
    # warned about. Writing a recap nothing can carry would only spend a model call.
    store = FakeSummaryStore()
    summarizer = FakeSummarizer()
    source = _source(messages=_messages(30), summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=15, memory_budget=0, source_budget=0))

    assert summarizer.folded == []
    assert store.saves == 0


@pytest.mark.asyncio
async def test_observe_does_nothing_on_an_empty_conversation() -> None:
    store = FakeSummaryStore()
    summarizer = FakeSummarizer()
    source = _source(messages=[], summary_store=store, summarizer=summarizer)

    await source.observe(_observe_context(turn=1, memory_budget=100, source_budget=25))

    assert summarizer.folded == []
    assert store.saves == 0


def test_the_high_water_share_must_be_a_share() -> None:
    with pytest.raises(ValueError):
        RollingSummarySource(
            summary_store=FakeSummaryStore(),
            conversation_store=FakeConversationStore([]),
            summarizer=FakeSummarizer(),
            token_counter=WordTokenCounter(),
            model_name=MODEL_NAME,
            high_water_share=1.5,
        )
