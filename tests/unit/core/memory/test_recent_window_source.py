from uuid import UUID

import pytest

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecallContext
from rp_engine.core.memory.recent_window_source import (
    MESSAGE_OVERHEAD_TOKENS,
    RecentWindowSource,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")


class FixedTokenCounter:
    """One token per word, so a test can state a budget in words."""

    async def count_tokens(self, text: str) -> int:
        return len(text.split())


def _message(
    content: str, *, role: ConversationRole = ConversationRole.USER
) -> ConversationMessage:
    return ConversationMessage(role=role, content=content)


def _context(messages: list[ConversationMessage], *, budget: int) -> MemoryRecallContext:
    return MemoryRecallContext(
        session_id=SESSION_ID,
        scenario_definition_id="scenario-1",
        recent_messages=tuple(messages),
        current_user_message="and then?",
        remaining_budget=budget,
    )


def _source() -> RecentWindowSource:
    return RecentWindowSource(token_counter=FixedTokenCounter())


@pytest.mark.asyncio
async def test_whole_history_is_replayed_when_it_fits() -> None:
    history = [_message("one two"), _message("three four")]

    fragments = await _source().recall(_context(history, budget=1000))

    assert len(fragments) == 1
    assert list(fragments[0].messages) == history


@pytest.mark.asyncio
async def test_only_the_newest_turns_that_fit_are_kept() -> None:
    history = [_message("oldest one"), _message("middle one"), _message("newest one")]
    # Each message costs two words plus the per-message overhead, so two fit and the
    # third does not.
    budget = 2 * (2 + MESSAGE_OVERHEAD_TOKENS) + 1

    fragments = await _source().recall(_context(history, budget=budget))

    kept = [message.content for message in fragments[0].messages]
    assert kept == ["middle one", "newest one"]


@pytest.mark.asyncio
async def test_kept_messages_stay_in_story_order() -> None:
    history = [_message(f"turn {index}") for index in range(5)]

    fragments = await _source().recall(_context(history, budget=1000))

    assert [message.content for message in fragments[0].messages] == [
        "turn 0",
        "turn 1",
        "turn 2",
        "turn 3",
        "turn 4",
    ]


@pytest.mark.asyncio
async def test_no_message_is_cut_in_half() -> None:
    history = [_message("a b c d e f g h")]

    fragments = await _source().recall(_context(history, budget=4))

    # The one message costs more than the budget, so the window returns nothing at all
    # rather than the first few words of a sentence.
    assert fragments == ()


@pytest.mark.asyncio
async def test_a_message_that_cannot_fit_stops_the_walk() -> None:
    # A very long turn in the middle of the story. Skipping it to keep the older turns
    # around it would put a story with a hole in it into the prompt.
    history = [
        _message("old one"),
        _message(" ".join(str(number) for number in range(100))),
        _message("new one"),
    ]

    fragments = await _source().recall(_context(history, budget=20))

    assert [message.content for message in fragments[0].messages] == ["new one"]


@pytest.mark.asyncio
async def test_the_reported_cost_covers_every_kept_message() -> None:
    history = [_message("one two"), _message("three")]

    fragments = await _source().recall(_context(history, budget=1000))

    assert fragments[0].tokens == (2 + MESSAGE_OVERHEAD_TOKENS) + (1 + MESSAGE_OVERHEAD_TOKENS)


@pytest.mark.asyncio
async def test_the_window_carries_turns_and_no_prompt_text() -> None:
    # Layer 00 recalls the conversation, which reaches the model as chat turns. Rendering
    # it into the system prompt instead would undo the assistant-role mapping.
    fragments = await _source().recall(_context([_message("hello")], budget=100))

    assert fragments[0].body == ""
    assert fragments[0].messages


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", [0, -10])
async def test_no_budget_recalls_nothing(budget: int) -> None:
    assert await _source().recall(_context([_message("hello")], budget=budget)) == ()


@pytest.mark.asyncio
async def test_an_empty_conversation_recalls_nothing() -> None:
    assert await _source().recall(_context([], budget=1000)) == ()


@pytest.mark.asyncio
async def test_observing_a_turn_does_nothing() -> None:
    # The window stores nothing of its own; the conversation store already has the turn.
    context = MemoryObserveContext(
        session_id=SESSION_ID, scenario_definition_id="scenario-1", turn=4
    )

    await _source().observe(context)
