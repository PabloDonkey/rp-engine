from pathlib import Path

import pytest

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.infrastructure.storage import JsonConversationStore


@pytest.mark.asyncio
async def test_json_store_saves_and_loads_messages(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    key = MemoryKey("session_12345")

    await store.save_message(
        key,
        ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
    )
    await store.save_message(
        key,
        ConversationMessage(role=ConversationRole.CHARACTER, content="hi", metadata={}),
    )

    loaded = await store.load_messages(key)

    assert loaded == [
        ConversationMessage(role=ConversationRole.USER, content="hello", metadata={}),
        ConversationMessage(role=ConversationRole.CHARACTER, content="hi", metadata={}),
    ]


@pytest.mark.asyncio
async def test_json_store_clear_removes_memory_file(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    key = MemoryKey("session_98765")

    await store.save_message(
        key,
        ConversationMessage(role=ConversationRole.CHARACTER, content="scene", metadata={}),
    )
    await store.clear(key)

    loaded = await store.load_messages(key)

    assert loaded == []


@pytest.mark.asyncio
async def test_json_store_preserves_metadata(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    key = MemoryKey("session_555")

    await store.save_message(
        key,
        ConversationMessage(
            role=ConversationRole.USER,
            content="I open the door",
            metadata={
                "user_id": "123456",
                "username": "alice",
                "display_name": "Alice",
            },
        ),
    )

    loaded = await store.load_messages(key)

    assert loaded == [
        ConversationMessage(
            role=ConversationRole.USER,
            content="I open the door",
            metadata={
                "user_id": "123456",
                "username": "alice",
                "display_name": "Alice",
            },
        )
    ]
