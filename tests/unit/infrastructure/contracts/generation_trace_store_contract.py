from uuid import UUID

from rp_engine.core.ports.generation_trace_store import GenerationTraceStore

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")


async def assert_generation_trace_store_contract(store: GenerationTraceStore) -> None:
    other_session_id = UUID("00000000-0000-0000-0000-000000000222")

    assert await store.list_for_session(SESSION_ID) == []

    await store.append(session_id=SESSION_ID, record={"turn": 1, "response": "a"})
    await store.append(session_id=SESSION_ID, record={"turn": 2, "response": "b"})
    await store.append(session_id=other_session_id, record={"turn": 1, "response": "c"})

    records = await store.list_for_session(SESSION_ID)
    assert [record["turn"] for record in records] == [1, 2]

    other_records = await store.list_for_session(other_session_id)
    assert [record["turn"] for record in other_records] == [1]


async def assert_generation_trace_delete_for_turn_contract(store: GenerationTraceStore) -> None:
    """Traces are deleted with the message they describe (admin panel, delete last turn)."""
    session_id = UUID("00000000-0000-0000-0000-0000000009a1")
    other_session = UUID("00000000-0000-0000-0000-0000000009b2")

    # A retried turn leaves more than one trace; both describe turn 2.
    await store.append(session_id=session_id, record={"turn": 1, "response": "one"})
    await store.append(session_id=session_id, record={"turn": 2, "response": "two-a"})
    await store.append(session_id=session_id, record={"turn": 2, "response": "two-b"})
    await store.append(session_id=other_session, record={"turn": 2, "response": "elsewhere"})

    assert await store.delete_for_turn(session_id=session_id, turn=2) == 2

    remaining = await store.list_for_session(session_id)
    assert [record["turn"] for record in remaining] == [1]
    # Scoped to its own session.
    assert len(await store.list_for_session(other_session)) == 1

    # Deleting a turn with no traces is not an error.
    assert await store.delete_for_turn(session_id=session_id, turn=99) == 0
