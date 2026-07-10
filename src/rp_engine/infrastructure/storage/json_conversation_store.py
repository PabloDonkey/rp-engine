import asyncio
import json
from pathlib import Path
from typing import Any, cast

from rp_engine.core.memory.models import ConversationMessage, MemoryKey
from rp_engine.core.ports.conversation_store import ConversationStore


class JsonConversationStore(ConversationStore):
    def __init__(self, base_path: Path | str = "data/memory") -> None:
        self._base_path = Path(base_path)
        self._lock = asyncio.Lock()

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        async with self._lock:
            messages = await self.load_messages(memory_key)
            messages.append(message)
            await self._write_messages(memory_key, messages)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        file_path = self._file_path(memory_key)
        if not file_path.exists():
            return []

        payload = await asyncio.to_thread(self._read_payload, file_path)
        raw_messages = cast(list[dict[str, Any]], payload.get("messages", []))
        messages: list[ConversationMessage] = []
        for raw in raw_messages:
            role = raw.get("role")
            content = raw.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append(ConversationMessage(role=role, content=content))
        return messages

    async def clear(self, memory_key: MemoryKey) -> None:
        async with self._lock:
            file_path = self._file_path(memory_key)
            if file_path.exists():
                await asyncio.to_thread(file_path.unlink)

    async def _write_messages(
        self,
        memory_key: MemoryKey,
        messages: list[ConversationMessage],
    ) -> None:
        file_path = self._file_path(memory_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ]
        }
        await asyncio.to_thread(self._write_payload, file_path, payload)

    def _file_path(self, memory_key: MemoryKey) -> Path:
        return self._base_path / f"{memory_key.value}.json"

    @staticmethod
    def _read_payload(file_path: Path) -> dict[str, object]:
        with file_path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)

        if isinstance(loaded, dict):
            return loaded
        return {"messages": []}

    @staticmethod
    def _write_payload(file_path: Path, payload: dict[str, object]) -> None:
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
