import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.role_profile import RoleProfile
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph
from rp_engine.core.world.world import World


class JsonScenarioDefinitionStore(ScenarioDefinitionStore):
    def __init__(self, base_path: Path | str = "data") -> None:
        self._scenarios_path = Path(base_path) / "scenarios"
        self._lock = asyncio.Lock()

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        scenario_file = self._scenarios_path / scenario_id / "definition.json"
        if not scenario_file.exists():
            return None

        payload = await asyncio.to_thread(self._read_payload, scenario_file)
        return self._to_scenario_definition(payload)

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
            scenario = self._to_scenario_definition(payload)
            if scenario is None:
                continue
            if scenario.owner_id == owner_id:
                scenarios.append(scenario)
        return scenarios

    async def save(self, scenario: ScenarioDefinition) -> None:
        async with self._lock:
            scenario_dir = self._scenarios_path / scenario.id
            scenario_dir.mkdir(parents=True, exist_ok=True)

            payload: dict[str, Any] = {
                "id": scenario.id,
                "owner_id": str(scenario.owner_id),
                "name": scenario.name,
                "description": scenario.description,
                "world": self._world_to_payload(scenario.world),
                "role_profiles": {
                    role: self._role_profile_to_payload(profile)
                    for role, profile in scenario.role_profiles.items()
                },
                "characters": {
                    role: self._character_to_payload(char)
                    for role, char in scenario.characters.items()
                },
                "rules": scenario.rules,
                "story_graph": self._story_graph_to_payload(scenario.story_graph),
                "initial_context": scenario.initial_context,
                "metadata": scenario.metadata,
            }
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

    @staticmethod
    def _to_scenario_definition(payload: dict[str, Any]) -> ScenarioDefinition | None:
        try:
            world = None
            if payload.get("world"):
                world_data = payload["world"]
                world = World(
                    id=world_data["id"],
                    name=world_data["name"],
                    description=world_data["description"],
                    rules=tuple(world_data.get("rules", [])),
                    metadata=world_data.get("metadata", {}),
                )

            role_profiles = {}
            for role, profile_data in payload.get("role_profiles", {}).items():
                role_profiles[role] = RoleProfile(
                    id=profile_data["id"],
                    name=profile_data["name"],
                    description=profile_data.get("description", ""),
                    objectives=tuple(profile_data.get("objectives", [])),
                    constraints=tuple(profile_data.get("constraints", [])),
                    metadata=profile_data.get("metadata", {}),
                )

            characters = {}
            if payload.get("characters"):
                for role, char_data in payload["characters"].items():
                    characters[role] = Character(
                        id=char_data["id"],
                        owner_id=UUID(char_data["owner_id"]),
                        visibility=CharacterVisibility(char_data["visibility"]),
                        name=char_data["name"],
                        description=char_data["description"],
                        personality=char_data["personality"],
                        greeting=char_data.get("greeting", ""),
                        metadata=char_data.get("metadata", {}),
                    )

            story_graph = JsonScenarioDefinitionStore._story_graph_from_payload(
                payload.get("story_graph")
            )

            return ScenarioDefinition(
                id=payload["id"],
                owner_id=UUID(payload["owner_id"]),
                name=payload["name"],
                description=payload["description"],
                world=world,
                role_profiles=role_profiles,
                characters=characters,
                rules=payload.get("rules", []),
                story_graph=story_graph,
                initial_context=payload.get("initial_context", ""),
                metadata=payload.get("metadata", {}),
            )
        except (KeyError, ValueError, TypeError):
            return None

    @staticmethod
    def _world_to_payload(world: World | None) -> dict[str, Any] | None:
        if world is None:
            return None
        return {
            "id": world.id,
            "name": world.name,
            "description": world.description,
            "rules": world.rules,
            "metadata": world.metadata,
        }

    @staticmethod
    def _role_profile_to_payload(profile: RoleProfile) -> dict[str, Any]:
        return {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "objectives": list(profile.objectives),
            "constraints": list(profile.constraints),
            "metadata": profile.metadata,
        }

    @staticmethod
    def _story_graph_to_payload(graph: StoryGraph | None) -> dict[str, Any] | None:
        if graph is None:
            return None
        return {
            "entry_beat_id": graph.entry_beat_id,
            "beats": {
                beat_id: {
                    "id": beat.id,
                    "description": beat.description,
                    "transitions": beat.transitions,
                    "metadata": beat.metadata,
                }
                for beat_id, beat in graph.beats.items()
            },
            "metadata": graph.metadata,
        }

    @staticmethod
    def _story_graph_from_payload(data: dict[str, Any] | None) -> StoryGraph | None:
        if not data:
            return None
        beats = {
            beat_id: StoryBeat(
                id=beat_data["id"],
                description=beat_data["description"],
                transitions=beat_data.get("transitions", {}),
                metadata=beat_data.get("metadata", {}),
            )
            for beat_id, beat_data in data.get("beats", {}).items()
        }
        return StoryGraph(
            beats=beats,
            entry_beat_id=data.get("entry_beat_id"),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def _character_to_payload(character: Character) -> dict[str, Any]:
        return {
            "id": character.id,
            "owner_id": str(character.owner_id),
            "visibility": character.visibility.value,
            "name": character.name,
            "description": character.description,
            "personality": character.personality,
            "greeting": character.greeting,
            "metadata": character.metadata,
        }
