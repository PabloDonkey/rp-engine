import asyncio
import json
from pathlib import Path
from uuid import UUID

from rp_engine.core.ports.generation_trace_store import GenerationTraceStore


class JsonGenerationTraceStore(GenerationTraceStore):
    def __init__(self, base_path: Path | str = "data/sessions") -> None:
        self._base_path = Path(base_path)
        self._lock = asyncio.Lock()

    async def append(self, *, session_id: UUID, record: dict[str, object]) -> None:
        async with self._lock:
            file_path = self._base_path / str(session_id) / "trace.jsonl"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._append_jsonl, file_path, record)

    async def list_for_session(self, session_id: UUID) -> list[dict[str, object]]:
        file_path = self._base_path / str(session_id) / "trace.jsonl"
        return await asyncio.to_thread(self._read_jsonl, file_path)

    @staticmethod
    def _append_jsonl(file_path: Path, record: dict[str, object]) -> None:
        with file_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=True))
            file.write("\n")

    @staticmethod
    def _read_jsonl(file_path: Path) -> list[dict[str, object]]:
        if not file_path.exists():
            return []
        records: list[dict[str, object]] = []
        with file_path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                loaded = json.loads(stripped)
                if isinstance(loaded, dict):
                    records.append(loaded)
        return records
