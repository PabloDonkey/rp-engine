import json
from pathlib import Path
from uuid import UUID

import pytest

from rp_engine.infrastructure.storage.json_generation_trace_store import JsonGenerationTraceStore


@pytest.mark.asyncio
async def test_generation_trace_store_appends_jsonl_records(tmp_path: Path) -> None:
    store = JsonGenerationTraceStore(base_path=tmp_path)
    session_id = UUID("00000000-0000-0000-0000-000000000111")

    await store.append(session_id=session_id, record={"turn": 1, "response": "a"})
    await store.append(session_id=session_id, record={"turn": 2, "response": "b"})

    trace_path = tmp_path / str(session_id) / "trace.jsonl"
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"turn": 1, "response": "a"}
    assert json.loads(lines[1]) == {"turn": 2, "response": "b"}
