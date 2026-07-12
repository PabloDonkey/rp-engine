import asyncio
import json
from pathlib import Path
from typing import Any, cast

from rp_engine.core.conversation.builder import ConversationBuilder
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.ports.conversation_store import ConversationStore


class JsonConversationStore(ConversationStore):
    def __init__(self, base_path: Path | str = "data/sessions") -> None:
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

        raw_messages = await asyncio.to_thread(self._read_jsonl_messages, file_path)
        messages: list[ConversationMessage] = []
        for raw in raw_messages:
            role = raw.get("role")
            content = raw.get("content")
            metadata = raw.get("metadata", {})
            if not isinstance(content, str):
                continue
            if not isinstance(role, str):
                continue
            if not isinstance(metadata, dict):
                metadata = {}

            normalized_metadata = {
                key: value
                for key, value in cast(dict[str, Any], metadata).items()
                if isinstance(key, str) and isinstance(value, str)
            }
            converted = ConversationBuilder.message_from_storage(
                role=role,
                content=content,
                metadata=normalized_metadata,
            )
            if converted is not None:
                messages.append(converted)
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
            "messages": [self._serialize_message(message) for message in messages]
        }
        await asyncio.to_thread(self._write_jsonl_payload, file_path, payload)

    @staticmethod
    def _serialize_message(message: ConversationMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "role": message.role.value,
            "content": message.content,
            "metadata": message.metadata,
        }
        return payload

    def _file_path(self, memory_key: MemoryKey) -> Path:
        if memory_key.value.startswith("session_"):
            session_id = memory_key.value.removeprefix("session_")
            return self._base_path / session_id / "history.jsonl"
        return self._base_path / memory_key.value / "history.jsonl"

    @staticmethod
    def _read_jsonl_messages(file_path: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with file_path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                loaded = json.loads(stripped)
                if isinstance(loaded, dict):
                    records.append(loaded)
        return records

    @staticmethod
    def _write_jsonl_payload(file_path: Path, payload: dict[str, object]) -> None:
        raw_messages = payload.get("messages", [])
        messages = cast(list[dict[str, object]], raw_messages)
        with file_path.open("w", encoding="utf-8") as file:
            for message in messages:
                file.write(json.dumps(message, ensure_ascii=True))
                file.write("\n")
