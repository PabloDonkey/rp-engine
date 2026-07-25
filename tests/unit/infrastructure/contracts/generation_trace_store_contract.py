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
