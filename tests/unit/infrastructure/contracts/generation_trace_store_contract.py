from uuid import UUID

from rp_engine.core.ports.generation_trace_store import GenerationTraceStore

SESSION_ID = UUID("00000000-0000-0000-0000-000000000111")


async def assert_generation_trace_store_contract(store: GenerationTraceStore) -> None:
    # The port is append-only; the contract just asserts multiple appends (same and
    # different sessions) are accepted without error.
    await store.append(session_id=SESSION_ID, record={"turn": 1, "response": "a"})
    await store.append(session_id=SESSION_ID, record={"turn": 2, "response": "b"})
    await store.append(
        session_id=UUID("00000000-0000-0000-0000-000000000222"),
        record={"turn": 1, "response": "c"},
    )
