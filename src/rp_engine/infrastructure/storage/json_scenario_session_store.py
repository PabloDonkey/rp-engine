import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind


class JsonScenarioSessionStore(ScenarioSessionStore):
    def __init__(self, base_path: Path | str = "data") -> None:
        self._sessions_path = Path(base_path) / "scenario_sessions"
        self._active_index_path = self._sessions_path / "active_by_owner.json"
        self._lock = asyncio.Lock()

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        session_file = self._sessions_path / str(session_id) / "session.json"
        if not session_file.exists():
            return None

        payload = await asyncio.to_thread(self._read_payload, session_file)
        return self._to_scenario_session(payload)

    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
    ) -> list[ScenarioSession]:
        sessions = []
        for session in await self._iter_sessions():
            if session.owner_kind == owner_kind and session.owner_id == owner_id:
                sessions.append(session)
        return sessions

    async def find_by_definition(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        for session in await self._iter_sessions():
            if (
                session.owner_kind == owner_kind
                and session.owner_id == owner_id
                and session.scenario_definition_id == scenario_definition_id
            ):
                return session
        return None

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        async with self._lock:
            session_dir = self._sessions_path / str(session.id)
            session_dir.mkdir(parents=True, exist_ok=True)

            payload: dict[str, Any] = {
                "id": str(session.id),
                "scenario_definition_id": session.scenario_definition_id,
                "owner_kind": session.owner_kind,
                "owner_id": str(session.owner_id),
                "active_participants": session.active_participants,
                "world_state": session.world_state,
                "story_progress": session.story_progress,
                "created_at": session.created_at.isoformat(),
                "metadata": session.metadata,
            }
            await asyncio.to_thread(
                self._write_payload,
                session_dir / "session.json",
                payload,
            )
            return session

    async def delete(self, session_id: UUID) -> None:
        async with self._lock:
            session_dir = self._sessions_path / str(session_id)
            if session_dir.exists():
                await asyncio.to_thread(self._delete_directory, session_dir)

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        async with self._lock:
            self._sessions_path.mkdir(parents=True, exist_ok=True)
            payload = await asyncio.to_thread(self._read_index, self._active_index_path)
            payload[f"{owner_kind}:{owner_id}"] = str(session_id)
            await asyncio.to_thread(self._write_payload, self._active_index_path, payload)

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        payload = await asyncio.to_thread(self._read_index, self._active_index_path)
        session_id = payload.get(f"{owner_kind}:{owner_id}")
        if not isinstance(session_id, str):
            return None
        try:
            parsed_id = UUID(session_id)
        except ValueError:
            return None
        return await self.get_by_id(parsed_id)

    async def _iter_sessions(self) -> list[ScenarioSession]:
        if not self._sessions_path.exists():
            return []
        sessions = []
        for directory in self._sessions_path.iterdir():
            if not directory.is_dir():
                continue
            session_file = directory / "session.json"
            if not session_file.exists():
                continue
            payload = await asyncio.to_thread(self._read_payload, session_file)
            session = self._to_scenario_session(payload)
            if session is not None:
                sessions.append(session)
        return sessions

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict)
            return data

    @staticmethod
    def _read_index(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _write_payload(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def _delete_directory(path: Path) -> None:
        if path.exists():
            import shutil

            shutil.rmtree(path)

    @staticmethod
    def _to_scenario_session(payload: dict[str, Any]) -> ScenarioSession | None:
        try:
            return ScenarioSession(
                id=UUID(payload["id"]),
                scenario_definition_id=payload["scenario_definition_id"],
                owner_kind=payload["owner_kind"],
                owner_id=UUID(payload["owner_id"]),
                active_participants=payload.get("active_participants", {}),
                world_state=payload.get("world_state", {}),
                story_progress=payload.get("story_progress", {}),
                created_at=datetime.fromisoformat(payload["created_at"]),
                metadata=payload.get("metadata", {}),
            )
        except (KeyError, ValueError, TypeError):
            return None
