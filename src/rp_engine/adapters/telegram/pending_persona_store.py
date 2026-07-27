import asyncio
import json
from pathlib import Path
from uuid import UUID


class TelegramPendingPersonaStore:
    """Remembers that an owner has a freshly-created session waiting for a persona reply.

    Telegram handling is otherwise stateless per message: a `/play` and the plain-text
    reply that follows it are two unrelated updates. This is the small piece of memory that
    links them, holding the session id the next reply belongs to. Keyed by
    `(owner_kind, owner_id)` like every other session-scoped lookup, so a second `/play`
    or `/clear` simply overwrites it and the abandoned prompt costs nothing.

    A transport concern, like `TelegramNarratorStore` it mirrors: it never reaches the
    domain or application layers.
    """

    def __init__(self, base_path: Path | str = "data") -> None:
        self._path = Path(base_path) / "telegram" / "pending_personas"
        self._lock = asyncio.Lock()

    async def get(self, *, owner_kind: str, owner_id: str) -> UUID | None:
        file = self._file(owner_kind, owner_id)
        if not file.exists():
            return None
        return await asyncio.to_thread(self._read, file)

    async def set(self, *, owner_kind: str, owner_id: str, session_id: UUID) -> None:
        async with self._lock:
            file = self._file(owner_kind, owner_id)
            await asyncio.to_thread(self._write, file, session_id)

    async def clear(self, *, owner_kind: str, owner_id: str) -> None:
        async with self._lock:
            file = self._file(owner_kind, owner_id)
            await asyncio.to_thread(self._delete, file)

    def _file(self, owner_kind: str, owner_id: str) -> Path:
        safe = f"{owner_kind}_{owner_id}".replace("/", "_")
        return self._path / f"{safe}.json"

    @staticmethod
    def _read(file: Path) -> UUID | None:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        session_id = payload.get("session_id") if isinstance(payload, dict) else None
        if not isinstance(session_id, str):
            return None
        try:
            return UUID(session_id)
        except ValueError:
            return None

    @staticmethod
    def _write(file: Path, session_id: UUID) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            json.dumps({"session_id": str(session_id)}, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _delete(file: Path) -> None:
        file.unlink(missing_ok=True)
