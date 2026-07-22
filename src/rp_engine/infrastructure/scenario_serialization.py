"""Shared (de)serialization between the domain scenario models and plain payloads.

Both the JSON stores and the PostgreSQL stores use these mappers so the two backends
stay byte-for-byte consistent. Field-level helpers are exposed for backends (like
PostgreSQL) that spread the nested structures across JSONB columns; whole-object
helpers are used by the JSON stores that persist a single document.
"""

from typing import Any
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.scenario.role_profile import RoleProfile
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph
from rp_engine.core.world.world import World


def world_to_payload(world: World | None) -> dict[str, Any] | None:
    if world is None:
        return None
    return {
        "id": world.id,
        "name": world.name,
        "description": world.description,
        "rules": list(world.rules),
        "metadata": world.metadata,
    }


def world_from_payload(data: dict[str, Any] | None) -> World | None:
    if not data:
        return None
    return World(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        rules=tuple(data.get("rules", [])),
        metadata=data.get("metadata", {}),
    )


def character_to_payload(character: Character) -> dict[str, Any]:
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


def character_from_payload(data: dict[str, Any]) -> Character:
    return Character(
        id=data["id"],
        owner_id=UUID(data["owner_id"]),
        visibility=CharacterVisibility(data["visibility"]),
        name=data["name"],
        description=data["description"],
        personality=data["personality"],
        greeting=data.get("greeting", ""),
        metadata=data.get("metadata", {}),
    )


def role_profile_to_payload(profile: RoleProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "objectives": list(profile.objectives),
        "constraints": list(profile.constraints),
        "metadata": profile.metadata,
    }


def role_profile_from_payload(data: dict[str, Any]) -> RoleProfile:
    return RoleProfile(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        objectives=tuple(data.get("objectives", [])),
        constraints=tuple(data.get("constraints", [])),
        metadata=data.get("metadata", {}),
    )


def story_graph_to_payload(graph: StoryGraph | None) -> dict[str, Any] | None:
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


def story_graph_from_payload(data: dict[str, Any] | None) -> StoryGraph | None:
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


def role_profiles_to_payload(profiles: dict[str, RoleProfile]) -> dict[str, Any]:
    return {role: role_profile_to_payload(profile) for role, profile in profiles.items()}


def role_profiles_from_payload(data: dict[str, Any]) -> dict[str, RoleProfile]:
    return {role: role_profile_from_payload(value) for role, value in data.items()}


def characters_to_payload(characters: dict[str, Character]) -> dict[str, Any]:
    return {role: character_to_payload(character) for role, character in characters.items()}


def characters_from_payload(data: dict[str, Any]) -> dict[str, Character]:
    return {role: character_from_payload(value) for role, value in data.items()}


def scenario_definition_to_payload(scenario: ScenarioDefinition) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "owner_id": str(scenario.owner_id),
        "name": scenario.name,
        "description": scenario.description,
        "world": world_to_payload(scenario.world),
        "role_profiles": role_profiles_to_payload(scenario.role_profiles),
        "characters": characters_to_payload(scenario.characters),
        "rules": scenario.rules,
        "story_graph": story_graph_to_payload(scenario.story_graph),
        "initial_context": scenario.initial_context,
        "metadata": scenario.metadata,
    }


def scenario_definition_from_payload(payload: dict[str, Any]) -> ScenarioDefinition | None:
    try:
        return ScenarioDefinition(
            id=payload["id"],
            owner_id=UUID(payload["owner_id"]),
            name=payload["name"],
            description=payload["description"],
            world=world_from_payload(payload.get("world")),
            role_profiles=role_profiles_from_payload(payload.get("role_profiles", {})),
            characters=characters_from_payload(payload.get("characters", {})),
            rules=payload.get("rules", []),
            story_graph=story_graph_from_payload(payload.get("story_graph")),
            initial_context=payload.get("initial_context", ""),
            metadata=payload.get("metadata", {}),
        )
    except (KeyError, ValueError, TypeError):
        return None


def scenario_session_to_payload(session: ScenarioSession) -> dict[str, Any]:
    return {
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


def scenario_session_from_payload(payload: dict[str, Any]) -> ScenarioSession | None:
    from datetime import datetime

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
