import asyncio
import json
from pathlib import Path
from typing import Any

from rp_engine.core.ports.world_store import WorldStore
from rp_engine.core.world.world import World


class JsonWorldStore(WorldStore):
    def __init__(self, base_path: Path | str = "data") -> None:
        self._worlds_path = Path(base_path) / "worlds"
        self._lock = asyncio.Lock()

    async def get_by_id(self, world_id: str) -> World | None:
        world_path = self._worlds_path / world_id / "world.json"
        if not world_path.exists():
            return None

        payload = await asyncio.to_thread(self._read_payload, world_path)
        return self._to_world(world_id=world_id, payload=payload)

    async def create_default(self, *, world_id: str) -> World:
        async with self._lock:
            existing = await self.get_by_id(world_id)
            if existing is not None:
                return existing

            world_dir = self._worlds_path / world_id
            world_dir.mkdir(parents=True, exist_ok=True)
            payload: dict[str, object] = {
                "name": "Default World",
                "description": "A flexible world with minimal predefined constraints.",
                "rules": [],
                "metadata": {},
            }
            await asyncio.to_thread(self._write_payload, world_dir / "world.json", payload)
            return World(
                id=world_id,
                name="Default World",
                description="A flexible world with minimal predefined constraints.",
                rules=(),
                metadata={},
            )

    @staticmethod
    def _to_world(*, world_id: str, payload: dict[str, Any]) -> World | None:
        name = payload.get("name")
        description = payload.get("description")
        rules = payload.get("rules", [])
        metadata = payload.get("metadata", {})
        if not isinstance(name, str) or not isinstance(description, str):
            return None
        if not isinstance(rules, list):
            rules = []
        normalized_rules = tuple(rule for rule in rules if isinstance(rule, str))
        if not isinstance(metadata, dict):
            metadata = {}
        normalized_metadata = {
            key: value
            for key, value in metadata.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        return World(
            id=world_id,
            name=name,
            description=description,
            rules=normalized_rules,
            metadata=normalized_metadata,
        )

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            return loaded
        return {}

    @staticmethod
    def _write_payload(path: Path, payload: dict[str, object]) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
