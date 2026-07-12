import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.ports.session_store import SessionStore
from rp_engine.core.session.session import Session


class JsonSessionStore(SessionStore):
    def __init__(self, base_path: Path | str = "data") -> None:
        self._sessions_path = Path(base_path) / "sessions"
        self._active_index_path = self._sessions_path / "active_by_user.json"
        self._lock = asyncio.Lock()

    async def get_by_id(self, session_id: UUID) -> Session | None:
        session_file = self._sessions_path / str(session_id) / "session.json"
        if not session_file.exists():
            return None

        payload = await asyncio.to_thread(self._read_payload, session_file)
        return self._to_session(payload)

    async def find_by_relationship(
        self,
        *,
        user_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None:
        if not self._sessions_path.exists():
            return None

        for directory in self._sessions_path.iterdir():
            if not directory.is_dir():
                continue
            session_file = directory / "session.json"
            if not session_file.exists():
                continue
            payload = await asyncio.to_thread(self._read_payload, session_file)
            candidate = self._to_session(payload)
            if candidate is None:
                continue
            if (
                candidate.user_id == user_id
                and candidate.character_id == character_id
                and candidate.world_id == world_id
            ):
                return candidate
        return None

    async def save(self, session: Session) -> Session:
        async with self._lock:
            session_dir = self._sessions_path / str(session.id)
            session_dir.mkdir(parents=True, exist_ok=True)
            payload: dict[str, object] = {
                "id": str(session.id),
                "user_id": str(session.user_id),
                "character_id": session.character_id,
                "world_id": session.world_id,
                "created_at": session.created_at.isoformat(),
                "metadata": session.metadata,
            }
            await asyncio.to_thread(self._write_payload, session_dir / "session.json", payload)
            return session

    async def set_active_for_user(self, *, user_id: UUID, session_id: UUID) -> None:
        async with self._lock:
            self._sessions_path.mkdir(parents=True, exist_ok=True)
            payload = await asyncio.to_thread(self._read_payload, self._active_index_path)
            payload[str(user_id)] = str(session_id)
            await asyncio.to_thread(self._write_payload, self._active_index_path, payload)

    async def get_active_for_user(self, *, user_id: UUID) -> Session | None:
        payload = await asyncio.to_thread(self._read_payload, self._active_index_path)
        session_id = payload.get(str(user_id))
        if not isinstance(session_id, str):
            return None

        try:
            parsed_id = UUID(session_id)
        except ValueError:
            return None
        return await self.get_by_id(parsed_id)

    @staticmethod
    def _to_session(payload: dict[str, Any]) -> Session | None:
        raw_id = payload.get("id")
        raw_user_id = payload.get("user_id")
        character_id = payload.get("character_id")
        world_id = payload.get("world_id")
        created_at = payload.get("created_at")
        metadata = payload.get("metadata", {})

        if not isinstance(raw_id, str):
            return None
        if not isinstance(raw_user_id, str):
            return None
        if not isinstance(character_id, str):
            return None
        if not isinstance(world_id, str):
            return None
        if not isinstance(created_at, str):
            return None
        if not isinstance(metadata, dict):
            metadata = {}

        normalized_metadata = {
            key: value
            for key, value in metadata.items()
            if isinstance(key, str) and isinstance(value, str)
        }

        try:
            return Session(
                id=UUID(raw_id),
                user_id=UUID(raw_user_id),
                character_id=character_id,
                world_id=world_id,
                created_at=datetime.fromisoformat(created_at),
                metadata=normalized_metadata,
            )
        except ValueError:
            return None

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            return loaded
        return {}

    @staticmethod
    def _write_payload(path: Path, payload: dict[str, object]) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
