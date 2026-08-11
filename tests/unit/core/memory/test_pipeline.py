import logging
from uuid import UUID

import pytest

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.context_budget import ContextBudget
from rp_engine.core.memory.fragment import PRIORITY_RECENT_WINDOW, MemoryFragment, MemorySystemId
from rp_engine.core.memory.pipeline import MemoryPipeline
from rp_engine.core.memory.recall_context import (
    MemoryObserveContext,
    MemoryRecall,
    MemoryRecallContext,
)
from rp_engine.core.memory.recent_window_source import MESSAGE_OVERHEAD_TOKENS, RecentWindowSource
from rp_engine.core.memory.settings import MemorySettings

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")
DEFINITION_ID = "scenario-1"


class FixedContextWindow:
    def __init__(self, tokens: int) -> None:
        self._tokens = tokens

    async def context_length(self) -> int:
        return self._tokens


class FixedTokenCounter:
    async def count_tokens(self, text: str) -> int:
        return len(text.split())


class StubSource:
    """A layer that returns what the test tells it to."""

    def __init__(
        self,
        source_id: MemorySystemId,
        *,
        body: str = "recalled",
        priority: int = 10,
        tokens: int = 1,
    ) -> None:
        self.id = source_id
        self.observed: list[int] = []
        self.seen_budget: int | None = None
        self._fragment = MemoryFragment(
            source=source_id,
            label=f"[{source_id}]",
            body=body,
            priority=priority,
            tokens=tokens,
        )

    async def recall(self, context: MemoryRecallContext) -> tuple[MemoryFragment, ...]:
        self.seen_budget = context.remaining_budget
        return (self._fragment,)

    async def observe(self, context: MemoryObserveContext) -> None:
        self.observed.append(context.turn)


class BrokenSource:
    def __init__(self, source_id: MemorySystemId) -> None:
        self.id = source_id

    async def recall(self, context: MemoryRecallContext) -> tuple[MemoryFragment, ...]:
        raise RuntimeError("layer is down")

    async def observe(self, context: MemoryObserveContext) -> None:
        raise RuntimeError("layer is down")


def _pipeline(sources: list[object], *, window: int = 1000, share: float = 1.0) -> MemoryPipeline:
    return MemoryPipeline(
        sources=sources,  # type: ignore[arg-type]
        context_budget=ContextBudget(context_window=FixedContextWindow(window), share=share),
    )


def _messages(count: int) -> list[ConversationMessage]:
    return [
        ConversationMessage(role=ConversationRole.USER, content=f"turn {index}")
        for index in range(count)
    ]


async def _recall(
    pipeline: MemoryPipeline,
    *,
    messages: list[ConversationMessage] | None = None,
    reserved_tokens: int = 0,
    settings: MemorySettings | None = None,
) -> MemoryRecall:
    return await pipeline.recall(
        session_id=SESSION_ID,
        scenario_definition_id=DEFINITION_ID,
        messages=messages if messages is not None else [],
        current_user_message="and then?",
        reserved_tokens=reserved_tokens,
        settings=settings or MemorySettings(),
    )


@pytest.mark.asyncio
async def test_memory_gets_what_the_rest_of_the_prompt_leaves() -> None:
    pipeline = _pipeline([StubSource("rolling_summary")], window=1000)

    recall = await _recall(
        pipeline,
        reserved_tokens=400,
        settings=MemorySettings(enabled_sources=("rolling_summary",)),
    )

    assert recall.budget_tokens == 600


@pytest.mark.asyncio
async def test_a_full_prompt_leaves_memory_nothing(caplog: pytest.LogCaptureFixture) -> None:
    # The static sections alone already fill the window. Memory returns nothing rather
    # than pushing the prompt past it — and says so, because this one is not routine: it
    # repeats on every turn of that scenario until someone shortens the card.
    pipeline = _pipeline([StubSource("rolling_summary")], window=100)

    with caplog.at_level(logging.WARNING):
        recall = await _recall(pipeline, messages=_messages(3), reserved_tokens=500)

    assert recall.messages == ()
    assert recall.fragments == ()
    assert recall.dropped_messages == 3
    assert "no room left for memory" in caplog.text


@pytest.mark.asyncio
async def test_budget_contention_is_resolved_by_priority() -> None:
    # Two layers want 8 tokens each and only 10 are free. The higher priority wins whole;
    # the loser is dropped whole rather than truncated.
    important = StubSource("rolling_summary", body="story so far", priority=50, tokens=8)
    optional = StubSource("lorebook", body="lore", priority=10, tokens=8)
    pipeline = _pipeline([optional, important], window=10)

    recall = await _recall(
        pipeline,
        settings=MemorySettings(enabled_sources=("rolling_summary", "lorebook")),
    )

    assert [fragment.source for fragment in recall.fragments] == ["rolling_summary"]
    assert recall.used_tokens == 8
    assert recall.dropped_fragment_tokens == 8


@pytest.mark.asyncio
async def test_the_recent_window_outranks_every_other_layer() -> None:
    # The conversation is what the reply continues, so it is never the fragment dropped.
    window = RecentWindowSource(token_counter=FixedTokenCounter())
    greedy = StubSource("lorebook", body="lore", priority=PRIORITY_RECENT_WINDOW - 1, tokens=90)
    pipeline = _pipeline([greedy, window], window=100)

    recall = await _recall(
        pipeline,
        messages=_messages(2),
        settings=MemorySettings(enabled_sources=("lorebook",)),
    )

    assert len(recall.messages) == 2
    assert recall.fragments == ()


@pytest.mark.asyncio
async def test_a_failing_layer_costs_its_own_context_and_not_the_turn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    working = StubSource("rolling_summary", body="story so far")
    pipeline = _pipeline([BrokenSource("lorebook"), working], window=1000)

    with caplog.at_level(logging.WARNING):
        recall = await _recall(
            pipeline,
            settings=MemorySettings(enabled_sources=("rolling_summary", "lorebook")),
        )

    assert [fragment.source for fragment in recall.fragments] == ["rolling_summary"]
    assert "lorebook" in caplog.text


@pytest.mark.asyncio
async def test_a_disabled_layer_is_never_asked() -> None:
    disabled = StubSource("lorebook")
    pipeline = _pipeline([disabled], window=1000)

    recall = await _recall(pipeline, settings=MemorySettings())

    assert disabled.seen_budget is None
    assert recall.fragments == ()


@pytest.mark.asyncio
async def test_the_recent_window_runs_even_though_it_has_no_toggle() -> None:
    window = RecentWindowSource(token_counter=FixedTokenCounter())
    pipeline = _pipeline([window], window=1000)

    recall = await _recall(pipeline, messages=_messages(2), settings=MemorySettings())

    assert len(recall.messages) == 2


@pytest.mark.asyncio
async def test_what_the_budget_dropped_is_reported_for_the_trace() -> None:
    window = RecentWindowSource(token_counter=FixedTokenCounter())
    # Each "turn N" message costs two words plus the per-message overhead.
    per_message = 2 + MESSAGE_OVERHEAD_TOKENS
    pipeline = _pipeline([window], window=2 * per_message)

    recall = await _recall(pipeline, messages=_messages(5))

    assert len(recall.messages) == 2
    assert recall.dropped_messages == 3
    assert recall.to_trace_record() == {
        "budget_tokens": 2 * per_message,
        "used_tokens": 2 * per_message,
        "dropped_messages": 3,
        "dropped_fragment_tokens": 0,
    }


@pytest.mark.asyncio
async def test_observe_reaches_the_enabled_layers_only() -> None:
    enabled = StubSource("rolling_summary")
    disabled = StubSource("lorebook")
    pipeline = _pipeline([enabled, disabled], window=1000)

    await pipeline.observe(
        MemoryObserveContext(session_id=SESSION_ID, scenario_definition_id=DEFINITION_ID, turn=7),
        settings=MemorySettings(enabled_sources=("rolling_summary",)),
    )

    assert enabled.observed == [7]
    assert disabled.observed == []


@pytest.mark.asyncio
async def test_a_failing_observe_is_logged_and_swallowed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = _pipeline([BrokenSource("lorebook")], window=1000)

    with caplog.at_level(logging.WARNING):
        await pipeline.observe(
            MemoryObserveContext(
                session_id=SESSION_ID, scenario_definition_id=DEFINITION_ID, turn=7
            ),
            settings=MemorySettings(enabled_sources=("lorebook",)),
        )

    assert "lorebook" in caplog.text
