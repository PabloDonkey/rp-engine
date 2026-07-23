import asyncio
import json
from pathlib import Path


class TelegramNarratorStore:
    """Tracks the Telegram message ids of the most recent narrator reply per chat.

    `/retry` uses this to delete the previous narrator message(s) before posting the
    regenerated reply, so the story reads as a single evolving message rather than a
    stack of alternatives. A narrator reply may be split across several Telegram
    messages, so each chat maps to a list of ids.

    This is a transport concern: it lives in the Telegram adapter and never reaches the
    domain or application layers.
    """

    def __init__(self, base_path: Path | str = "data") -> None:
        self._path = Path(base_path) / "telegram" / "narrator_messages"
        self._lock = asyncio.Lock()

    async def get(self, *, chat_id: str) -> list[int]:
        file = self._file(chat_id)
        if not file.exists():
            return []
        return await asyncio.to_thread(self._read, file)

    async def set(self, *, chat_id: str, message_ids: list[int]) -> None:
        async with self._lock:
            file = self._file(chat_id)
            await asyncio.to_thread(self._write, file, message_ids)

    async def clear(self, *, chat_id: str) -> None:
        async with self._lock:
            file = self._file(chat_id)
            await asyncio.to_thread(self._delete, file)

    def _file(self, chat_id: str) -> Path:
        safe = chat_id.replace("/", "_")
        return self._path / f"{safe}.json"

    @staticmethod
    def _read(file: Path) -> list[int]:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        message_ids = payload.get("message_ids") if isinstance(payload, dict) else None
        if not isinstance(message_ids, list):
            return []
        return [value for value in message_ids if isinstance(value, int)]

    @staticmethod
    def _write(file: Path, message_ids: list[int]) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            json.dumps({"message_ids": message_ids}, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _delete(file: Path) -> None:
        file.unlink(missing_ok=True)
