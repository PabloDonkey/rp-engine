import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.infrastructure.scenario_serialization import (
    scenario_definition_from_payload,
    scenario_definition_to_payload,
)


class JsonScenarioDefinitionStore(ScenarioDefinitionStore):
    def __init__(self, base_path: Path | str = "data") -> None:
        self._scenarios_path = Path(base_path) / "scenarios"
        self._lock = asyncio.Lock()

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        scenario_file = self._scenarios_path / scenario_id / "definition.json"
        if not scenario_file.exists():
            return None

        payload = await asyncio.to_thread(self._read_payload, scenario_file)
        return scenario_definition_from_payload(payload)

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        if not self._scenarios_path.exists():
            return []

        scenarios = []
        for directory in self._scenarios_path.iterdir():
            if not directory.is_dir():
                continue
            scenario_file = directory / "definition.json"
            if not scenario_file.exists():
                continue
            payload = await asyncio.to_thread(self._read_payload, scenario_file)
            scenario = scenario_definition_from_payload(payload)
            if scenario is None:
                continue
            if scenario.owner_id == owner_id:
                scenarios.append(scenario)
        return scenarios

    async def save(self, scenario: ScenarioDefinition) -> None:
        async with self._lock:
            scenario_dir = self._scenarios_path / scenario.id
            scenario_dir.mkdir(parents=True, exist_ok=True)
            payload = scenario_definition_to_payload(scenario)
            await asyncio.to_thread(
                self._write_payload,
                scenario_dir / "definition.json",
                payload,
            )

    async def delete(self, scenario_id: str) -> None:
        async with self._lock:
            scenario_dir = self._scenarios_path / scenario_id
            if scenario_dir.exists():
                await asyncio.to_thread(self._delete_directory, scenario_dir)

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict)
            return data

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
