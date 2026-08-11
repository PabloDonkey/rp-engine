"""Shared (de)serialization between the domain scenario models and plain payloads.

Both the JSON stores and the PostgreSQL stores use these mappers so the two backends
stay byte-for-byte consistent. Field-level helpers are exposed for backends (like
PostgreSQL) that spread the nested structures across JSONB columns; whole-object
helpers are used by the JSON stores that persist a single document.
"""

from typing import Any, cast, get_args
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.memory.fragment import ToggleableMemorySystemId
from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import (
    LANGUAGE_AUTO,
    ScenarioRule,
    SessionDirectives,
)
from rp_engine.core.scenario.story_graph import StoryBeat, StoryGraph
from rp_engine.core.scenario.visibility import ScenarioVisibility
from rp_engine.core.world.world import World

# The layer names a stored payload may name, read off the type so the two cannot drift.
TOGGLEABLE_MEMORY_SOURCE_IDS: frozenset[str] = frozenset(get_args(ToggleableMemorySystemId))


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
        "name": character.name,
        "description": character.description,
        "personality": character.personality,
        "greeting": character.greeting,
        "metadata": character.metadata,
    }


def character_from_payload(data: dict[str, Any]) -> Character:
    return Character(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        personality=data["personality"],
        greeting=data.get("greeting", ""),
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
        "characters": characters_to_payload(scenario.characters),
        "rules": scenario.rules,
        "story_graph": story_graph_to_payload(scenario.story_graph),
        "initial_context": scenario.initial_context,
        "visibility": scenario.visibility.value,
        "allowed_group_chat_ids": list(scenario.allowed_group_chat_ids),
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
            characters=characters_from_payload(payload.get("characters", {})),
            rules=payload.get("rules", []),
            story_graph=story_graph_from_payload(payload.get("story_graph")),
            initial_context=payload.get("initial_context", ""),
            visibility=ScenarioVisibility(payload.get("visibility", ScenarioVisibility.PUBLIC)),
            allowed_group_chat_ids=tuple(payload.get("allowed_group_chat_ids", ())),
            metadata=payload.get("metadata", {}),
        )
    except (KeyError, ValueError, TypeError):
        return None


def session_directives_to_payload(directives: SessionDirectives) -> dict[str, Any]:
    return {
        "language": directives.language,
        "rules": [{"id": rule.id, "text": rule.text} for rule in directives.rules],
        "director_instructions": list(directives.director_instructions),
    }


def session_directives_from_payload(data: dict[str, Any] | None) -> SessionDirectives:
    """Directives are additive to an existing session, so a missing or malformed payload
    degrades to the defaults rather than failing the whole session load."""
    if not data:
        return SessionDirectives()
    rules = tuple(
        ScenarioRule(id=str(rule["id"]), text=str(rule["text"]))
        for rule in data.get("rules", [])
        if isinstance(rule, dict) and "id" in rule and "text" in rule
    )
    return SessionDirectives(
        language=str(data.get("language", LANGUAGE_AUTO)),
        rules=rules,
        director_instructions=_director_instructions_from_payload(data),
    )


def _director_instructions_from_payload(data: dict[str, Any]) -> tuple[str, ...]:
    """Read the queued director notes, tolerating the pre-S020 single-string key.

    Stored sessions were converted by migration `20260802_0011`, so the legacy key is only
    expected from a session *export file* written before the notes could stack — a transfer
    format outlives the schema it was dumped from, and one archived note is worth keeping.
    """
    queued = data.get("director_instructions")
    if isinstance(queued, list):
        return tuple(str(note).strip() for note in queued if str(note).strip())
    legacy = str(data.get("director_instruction", "")).strip()
    return (legacy,) if legacy else ()


def memory_settings_to_payload(memory: MemorySettings) -> dict[str, Any]:
    return {"enabled_sources": list(memory.enabled_sources)}


def memory_settings_from_payload(data: dict[str, Any] | None) -> MemorySettings:
    """Read which memory layers a session runs.

    Additive like the directives above: a session stored before S022, or one naming a
    layer this build does not have, degrades to the defaults rather than failing the whole
    session load. An unknown name is dropped, not kept — keeping it would let a payload
    smuggle a value the type says is impossible.
    """
    if not data:
        return MemorySettings()
    raw = data.get("enabled_sources")
    if not isinstance(raw, list):
        return MemorySettings()
    enabled = tuple(
        source
        for source in raw
        if isinstance(source, str) and source in TOGGLEABLE_MEMORY_SOURCE_IDS
    )
    return MemorySettings(enabled_sources=cast(tuple[ToggleableMemorySystemId, ...], enabled))


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
        "updated_at": session.updated_at.isoformat(),
        "deleted_at": session.deleted_at.isoformat() if session.deleted_at is not None else None,
        "metadata": session.metadata,
        "directives": session_directives_to_payload(session.directives),
        "memory": memory_settings_to_payload(session.memory),
        "user_persona_name": session.user_persona_name,
        "user_persona_description": session.user_persona_description,
    }


def scenario_session_from_payload(payload: dict[str, Any]) -> ScenarioSession | None:
    from datetime import datetime

    try:
        created_at = datetime.fromisoformat(payload["created_at"])
        # Both lifecycle stamps are additive (S016): payloads exported before they existed
        # date the session from its creation and count as live, which is what they were.
        raw_updated_at = payload.get("updated_at")
        raw_deleted_at = payload.get("deleted_at")
        return ScenarioSession(
            id=UUID(payload["id"]),
            scenario_definition_id=payload["scenario_definition_id"],
            owner_kind=payload["owner_kind"],
            owner_id=UUID(payload["owner_id"]),
            active_participants=payload.get("active_participants", {}),
            world_state=payload.get("world_state", {}),
            story_progress=payload.get("story_progress", {}),
            created_at=created_at,
            updated_at=datetime.fromisoformat(raw_updated_at) if raw_updated_at else created_at,
            deleted_at=datetime.fromisoformat(raw_deleted_at) if raw_deleted_at else None,
            metadata=payload.get("metadata", {}),
            directives=session_directives_from_payload(payload.get("directives")),
            memory=memory_settings_from_payload(payload.get("memory")),
            user_persona_name=_optional_text(payload.get("user_persona_name")),
            user_persona_description=_optional_text(payload.get("user_persona_description")),
        )
    except (KeyError, ValueError, TypeError):
        return None


def _optional_text(value: Any) -> str | None:
    """Normalize an optional free-text field: absent, null and blank all mean "unset"."""
    if not isinstance(value, str):
        return None
    return value.strip() or None
