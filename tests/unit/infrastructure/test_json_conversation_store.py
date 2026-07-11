from pathlib import Path

import pytest

from rp_engine.core.memory.models import ConversationMessage, MemoryKey
from rp_engine.infrastructure.storage import JsonConversationStore


@pytest.mark.asyncio
async def test_json_store_saves_and_loads_messages(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    key = MemoryKey("user_12345")

    await store.save_message(key, ConversationMessage(role="user", content="hello"))
    await store.save_message(key, ConversationMessage(role="assistant", content="hi"))

    loaded = await store.load_messages(key)

    assert loaded == [
        ConversationMessage(role="user", content="hello"),
        ConversationMessage(role="assistant", content="hi"),
    ]


@pytest.mark.asyncio
async def test_json_store_clear_removes_memory_file(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    key = MemoryKey("group_-98765")

    await store.save_message(key, ConversationMessage(role="assistant", content="scene"))
    await store.clear(key)

    loaded = await store.load_messages(key)

    assert loaded == []


@pytest.mark.asyncio
async def test_json_store_preserves_optional_user_metadata(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    key = MemoryKey("group_-555")

    await store.save_message(
        key,
        ConversationMessage(
            role="user",
            content="I open the door",
            user_id="123456",
            username="alice",
            display_name="Alice",
        ),
    )

    loaded = await store.load_messages(key)

    assert loaded == [
        ConversationMessage(
            role="user",
            content="I open the door",
            user_id="123456",
            username="alice",
            display_name="Alice",
        )
    ]
