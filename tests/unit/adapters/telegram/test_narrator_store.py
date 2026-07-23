from pathlib import Path

import pytest

from rp_engine.adapters.telegram.narrator_store import TelegramNarratorStore


@pytest.mark.asyncio
async def test_get_missing_returns_empty(tmp_path: Path) -> None:
    store = TelegramNarratorStore(base_path=tmp_path)
    assert await store.get(chat_id="42") == []


@pytest.mark.asyncio
async def test_set_then_get_round_trip(tmp_path: Path) -> None:
    store = TelegramNarratorStore(base_path=tmp_path)
    await store.set(chat_id="42", message_ids=[10, 11, 12])
    assert await store.get(chat_id="42") == [10, 11, 12]


@pytest.mark.asyncio
async def test_set_overwrites_previous(tmp_path: Path) -> None:
    store = TelegramNarratorStore(base_path=tmp_path)
    await store.set(chat_id="42", message_ids=[1, 2])
    await store.set(chat_id="42", message_ids=[3])
    assert await store.get(chat_id="42") == [3]


@pytest.mark.asyncio
async def test_clear_removes_entry(tmp_path: Path) -> None:
    store = TelegramNarratorStore(base_path=tmp_path)
    await store.set(chat_id="42", message_ids=[1])
    await store.clear(chat_id="42")
    assert await store.get(chat_id="42") == []


@pytest.mark.asyncio
async def test_is_per_chat(tmp_path: Path) -> None:
    store = TelegramNarratorStore(base_path=tmp_path)
    await store.set(chat_id="-100", message_ids=[7])
    await store.set(chat_id="42", message_ids=[9])
    assert await store.get(chat_id="-100") == [7]
    assert await store.get(chat_id="42") == [9]


@pytest.mark.asyncio
async def test_clear_missing_is_noop(tmp_path: Path) -> None:
    store = TelegramNarratorStore(base_path=tmp_path)
    await store.clear(chat_id="nope")
    assert await store.get(chat_id="nope") == []
