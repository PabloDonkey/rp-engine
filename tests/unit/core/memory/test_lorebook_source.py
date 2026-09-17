"""Pure-Python coverage of `LorebookSource.recall` against a fake `LorebookStore`.

No Postgres here on purpose: full-text matching itself is the Postgres store's job and
belongs in a contract test run against a real database (left as a TODO for the engine
testing rework in progress elsewhere). This file only covers what `LorebookSource` does
before and after calling the store: building the recall window, and turning matched
entries into fragments.
"""

from uuid import UUID

import pytest

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.fragment import PRIORITY_LOREBOOK
from rp_engine.core.memory.lorebook_source import LORE_LABEL, LorebookSource
from rp_engine.core.memory.recall_context import MemoryRecallContext
from rp_engine.core.scenario.lore_entry import LoreEntry

SESSION_ID = UUID("00000000-0000-0000-0000-000000000222")
DEFINITION_ID = "jane-butcher-shop"


class WordTokenCounter:
    async def count_tokens(self, text: str) -> int:
        return len(text.split())


def _entry(entry_id: str = "jane_accident") -> LoreEntry:
    return LoreEntry.create(
        entry_id=entry_id,
        scenario_definition_id=DEFINITION_ID,
        title="The Accident",
        content="Jane once hurt someone she was trying to protect.",
        trigger_keys=["hurting someone", "Jane's strength"],
    )


class FakeLorebookStore:
    """Records what it was asked to match, and returns whatever the test configured."""

    def __init__(self, entries: tuple[LoreEntry, ...] = ()) -> None:
        self._entries = entries
        self.calls: list[tuple[str, str, int]] = []

    async def find_matching(
        self, scenario_definition_id: str, recall_text: str, *, limit: int
    ) -> tuple[LoreEntry, ...]:
        self.calls.append((scenario_definition_id, recall_text, limit))
        return self._entries

    async def list_for_scenario(self, scenario_definition_id: str) -> tuple[LoreEntry, ...]:
        raise NotImplementedError

    async def get(self, scenario_definition_id: str, entry_id: str) -> LoreEntry | None:
        raise NotImplementedError

    async def save(self, entry: LoreEntry) -> LoreEntry:
        raise NotImplementedError

    async def delete(self, scenario_definition_id: str, entry_id: str) -> None:
        raise NotImplementedError


def _message(text: str, role: ConversationRole = ConversationRole.USER) -> ConversationMessage:
    return ConversationMessage(role=role, content=text)


def _context(
    *,
    recent_messages: tuple[ConversationMessage, ...] = (),
    current_user_message: str = "",
    remaining_budget: int = 1000,
) -> MemoryRecallContext:
    return MemoryRecallContext(
        session_id=SESSION_ID,
        scenario_definition_id=DEFINITION_ID,
        recent_messages=recent_messages,
        current_user_message=current_user_message,
        remaining_budget=remaining_budget,
    )


@pytest.mark.asyncio
async def test_no_budget_returns_nothing_without_asking_the_store() -> None:
    store = FakeLorebookStore((_entry(),))
    source = LorebookSource(store=store, token_counter=WordTokenCounter())

    fragments = await source.recall(_context(remaining_budget=0))

    assert fragments == ()
    assert store.calls == []


@pytest.mark.asyncio
async def test_blank_recall_text_returns_nothing_without_asking_the_store() -> None:
    store = FakeLorebookStore((_entry(),))
    source = LorebookSource(store=store, token_counter=WordTokenCounter())

    fragments = await source.recall(_context(current_user_message="   "))

    assert fragments == ()
    assert store.calls == []


@pytest.mark.asyncio
async def test_empty_match_returns_nothing() -> None:
    store = FakeLorebookStore(())
    source = LorebookSource(store=store, token_counter=WordTokenCounter())

    fragments = await source.recall(_context(current_user_message="why is everyone afraid?"))

    assert fragments == ()


@pytest.mark.asyncio
async def test_matched_entry_becomes_one_fragment_with_the_layer_priority() -> None:
    store = FakeLorebookStore((_entry(),))
    source = LorebookSource(store=store, token_counter=WordTokenCounter())

    fragments = await source.recall(_context(current_user_message="why are you so strong?"))

    assert len(fragments) == 1
    fragment = fragments[0]
    assert fragment.source == "lorebook"
    assert fragment.label == LORE_LABEL
    assert fragment.priority == PRIORITY_LOREBOOK
    assert fragment.body == "The Accident: Jane once hurt someone she was trying to protect."
    assert fragment.tokens == len(fragment.body.split())


@pytest.mark.asyncio
async def test_recall_text_is_the_player_message_plus_a_short_tail() -> None:
    store = FakeLorebookStore(())
    source = LorebookSource(store=store, token_counter=WordTokenCounter())
    # Five prior messages; only the last four should make it into the recall window.
    history = tuple(_message(f"turn{i}") for i in range(5))

    await source.recall(_context(recent_messages=history, current_user_message="now"))

    assert len(store.calls) == 1
    scenario_id, recall_text, limit = store.calls[0]
    assert scenario_id == DEFINITION_ID
    assert recall_text == "turn1 turn2 turn3 turn4 now"
    assert limit == 3


@pytest.mark.asyncio
async def test_multiple_matches_each_become_their_own_fragment() -> None:
    entries = (_entry("jane_accident"), _entry("jane_lost_friendship"))
    store = FakeLorebookStore(entries)
    source = LorebookSource(store=store, token_counter=WordTokenCounter())

    fragments = await source.recall(_context(current_user_message="tell me about your past"))

    assert len(fragments) == 2
    assert all(fragment.label == LORE_LABEL for fragment in fragments)
