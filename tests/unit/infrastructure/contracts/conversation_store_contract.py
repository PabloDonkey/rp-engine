from typing import cast

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.ports.conversation_store import ConversationStore


async def assert_conversation_store_contract(store: ConversationStore) -> None:
    key = MemoryKey("session_12345")
    assert await store.load_messages(key) == []

    # Order is preserved across many messages.
    messages = [
        ConversationMessage(role=ConversationRole.USER, content=f"turn {index}", metadata={})
        for index in range(10)
    ]
    for message in messages:
        await store.save_message(key, message)
    assert await store.load_messages(key) == messages

    # Metadata with a non-str value is dropped on load; str/str entries survive. (A non-str
    # *key* can't reach storage in the first place: both backends round-trip metadata through
    # JSON-object semantics, which coerce dict keys to strings before the filter ever runs.)
    dirty_metadata = cast("dict[str, str]", {"keep": "value", "drop_int_value": 42})
    dirty_key = MemoryKey("session_dirty")
    await store.save_message(
        dirty_key,
        ConversationMessage(role=ConversationRole.USER, content="hi", metadata=dirty_metadata),
    )
    assert await store.load_messages(dirty_key) == [
        ConversationMessage(role=ConversationRole.USER, content="hi", metadata={"keep": "value"})
    ]

    # clear() only wipes the target key; a sibling key survives untouched.
    other_key = MemoryKey("session_other")
    await store.save_message(
        other_key,
        ConversationMessage(role=ConversationRole.CHARACTER, content="untouched", metadata={}),
    )
    await store.clear(key)
    assert await store.load_messages(key) == []
    assert await store.load_messages(other_key) == [
        ConversationMessage(role=ConversationRole.CHARACTER, content="untouched", metadata={})
    ]
