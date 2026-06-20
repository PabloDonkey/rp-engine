"""REST API server for rp-engine."""

from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, request
from flask_cors import CORS

from app.config import config
from engine.orchestrator import Orchestrator
from llm.client import LMStudioClient
from memory.character import CharacterManager
from memory.session import SessionManager
from memory.world import WorldManager

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Initialize managers
session_manager = SessionManager(config.SESSION_DIR)
character_manager = CharacterManager(config.CHARACTERS_DIR)
world_manager = WorldManager(config.WORLDS_DIR)

# Global orchestrator instance (loaded per request)
_orchestrator: Orchestrator | None = None


def get_orchestrator(session_id: str) -> Orchestrator:
    """Get or create orchestrator for a session.

    Args:
        session_id: Session ID to load

    Returns:
        Orchestrator instance

    Raises:
        ValueError: If session or character not found
    """
    global _orchestrator

    # Load session, character, world
    session = session_manager.load_session(session_id)
    if not session:
        raise ValueError(f"Session '{session_id}' not found")

    character = character_manager.load_character(session.character_name)
    if not character:
        raise ValueError(f"Character '{session.character_name}' not found")

    world = None
    if session.world_name:
        world = world_manager.load_world(session.world_name)

    # Initialize LLM client
    llm_client = LMStudioClient(config.LM_STUDIO_API_URL)

    # Create orchestrator
    _orchestrator = Orchestrator(
        llm_client=llm_client,
        session=session,
        character=character,
        world=world,
        model="local-model",
    )

    return _orchestrator


@app.route("/health", methods=["GET"])
def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Status response
    """
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.route("/api/sessions", methods=["GET"])
def list_sessions() -> dict[str, list[str]]:
    """List all sessions.

    Returns:
        List of session IDs
    """
    sessions = session_manager.list_sessions()
    return {"sessions": sessions}


@app.route("/api/sessions", methods=["POST"])
def create_session() -> dict[str, Any]:
    """Create a new session.

    JSON body:
        {
            "session_id": "my_session",
            "character_name": "Alice",
            "world_name": "Wonderland" (optional)
        }

    Returns:
        Created session data
    """
    data = request.get_json() or {}

    session_id = data.get("session_id", "default")
    character_name = data.get("character_name", "NPC")
    world_name = data.get("world_name", None)

    # Create session
    session = session_manager.create_session(
        session_id=session_id,
        character_name=character_name,
        world_name=world_name,
    )

    return {
        "session": {
            "id": session.session_id,
            "character": session.character_name,
            "world": session.world_name,
            "messages": session.message_count(),
        }
    }


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str) -> dict[str, Any] | tuple[dict[str, str], int]:
    """Get session details.

    Args:
        session_id: Session ID

    Returns:
        Session data with messages, or error with 404 status
    """
    session = session_manager.load_session(session_id)
    if not session:
        return {"error": f"Session '{session_id}' not found"}, 404

    messages = [
        {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
        for msg in session.messages
    ]

    return {
        "session": {
            "id": session.session_id,
            "character": session.character_name,
            "world": session.world_name,
            "messages": messages,
            "created_at": session.created_at.isoformat(),
        }
    }


@app.route("/api/sessions/<session_id>/message", methods=["POST"])
def send_message(session_id: str) -> dict[str, Any] | tuple[dict[str, str], int]:
    """Send a message and get LLM response.

    JSON body:
        {
            "content": "Hello, how are you?"
        }

    Args:
        session_id: Session ID

    Returns:
        LLM response, or error with status code
    """
    try:
        data = request.get_json() or {}
        user_message = data.get("content", "").strip()

        if not user_message:
            return {"error": "Message content required"}, 400

        # Get orchestrator
        orchestrator = get_orchestrator(session_id)

        # Get response
        response = orchestrator.step(user_message)

        # Save session
        session_manager.save_session(orchestrator.session)

        return {
            "message": {
                "user": user_message,
                "assistant": response,
                "timestamp": datetime.now().isoformat(),
            }
        }

    except ValueError as e:
        return {"error": str(e)}, 404
    except Exception as e:
        return {"error": f"Error processing message: {str(e)}"}, 500


@app.route("/api/characters", methods=["GET"])
def list_characters() -> dict[str, list[str]]:
    """List all characters.

    Returns:
        List of character names
    """
    char_dir = Path(config.CHARACTERS_DIR)
    characters = [f.stem for f in char_dir.glob("*.json") if f.is_file()]
    return {"characters": sorted(characters)}


@app.route("/api/characters", methods=["POST"])
def create_character() -> dict[str, Any]:
    """Create a new character.

    JSON body:
        {
            "name": "Alice",
            "personality": "Curious and adventurous",
            "tone": "Whimsical"
        }

    Returns:
        Created character data
    """
    data = request.get_json() or {}

    name = data.get("name", "Character")
    personality = data.get("personality", "Neutral")
    tone = data.get("tone", "Conversational")
    system_prompt = data.get("system_prompt", "You are a helpful AI assistant.")
    introduction = data.get("introduction", "Hello! I'm here to chat.")

    character = character_manager.create_character(
        name=name,
        personality=personality,
        tone=tone,
        system_prompt=system_prompt,
        introduction=introduction,
    )

    return {
        "character": {
            "name": character.name,
            "personality": character.personality,
            "tone": character.tone,
            "system_prompt": character.system_prompt,
            "introduction": character.introduction,
            "relationship_level": character.relationship_level,
            "notes": character.notes,
        }
    }


@app.route("/api/characters/<name>", methods=["PUT"])
def update_character(name: str) -> dict[str, Any] | tuple[dict[str, str], int]:
    """Update a character.

    Args:
        name: Character name

    Returns:
        Updated character data, or error with 404 status
    """
    character = character_manager.load_character(name)
    if not character:
        return {"error": f"Character '{name}' not found"}, 404

    data = request.get_json() or {}
    character.personality = data.get("personality", character.personality)
    character.tone = data.get("tone", character.tone)
    character.system_prompt = data.get(
        "system_prompt", character.system_prompt
    )
    character.introduction = data.get("introduction", character.introduction)
    character.notes = data.get("notes", character.notes)

    character_manager.save_character(character)

    return {
        "character": {
            "name": character.name,
            "personality": character.personality,
            "tone": character.tone,
            "system_prompt": character.system_prompt,
            "introduction": character.introduction,
            "relationship_level": character.relationship_level,
            "notes": character.notes,
        }
    }


@app.route("/api/characters/<name>", methods=["DELETE"])
def delete_character(name: str) -> dict[str, str] | tuple[dict[str, str], int]:
    """Delete a character.

    Args:
        name: Character name

    Returns:
        Success message, or error with 404 status
    """
    filepath = Path(config.CHARACTERS_DIR) / f"{name}.json"
    if not filepath.exists():
        return {"error": f"Character '{name}' not found"}, 404

    filepath.unlink()
    return {"message": f"Character '{name}' deleted"}


@app.route("/api/characters/<name>", methods=["GET"])
def get_character(name: str) -> dict[str, Any] | tuple[dict[str, str], int]:
    """Get character details.

    Args:
        name: Character name

    Returns:
        Character data, or error with 404 status
    """
    character = character_manager.load_character(name)
    if not character:
        return {"error": f"Character '{name}' not found"}, 404

    return {
        "character": {
            "name": character.name,
            "personality": character.personality,
            "tone": character.tone,
            "relationship_level": character.relationship_level,
        }
    }


@app.route("/api/worlds", methods=["GET"])
def list_worlds() -> dict[str, list[str]]:
    """List all worlds.

    Returns:
        List of world names
    """
    world_dir = Path(config.WORLDS_DIR)
    worlds = [f.stem for f in world_dir.glob("*.json") if f.is_file()]
    return {"worlds": sorted(worlds)}


@app.route("/api/worlds", methods=["POST"])
def create_world() -> dict[str, Any]:
    """Create a new world.

    JSON body:
        {
            "name": "Wonderland",
            "description": "A magical realm..."
        }

    Returns:
        Created world data
    """
    data = request.get_json() or {}

    name = data.get("name", "World")
    description = data.get("description", "")

    world = world_manager.create_world(name=name, description=description)

    return {
        "world": {
            "name": world.name,
            "description": world.description,
            "events": len(world.events),
            "flags": len(world.flags),
        }
    }


@app.route("/api/worlds/<name>", methods=["GET"])
def get_world(name: str) -> dict[str, Any] | tuple[dict[str, str], int]:
    """Get world details.

    Args:
        name: World name

    Returns:
        World data, or error with 404 status
    """
    world = world_manager.load_world(name)
    if not world:
        return {"error": f"World '{name}' not found"}, 404

    return {
        "world": {
            "name": world.name,
            "description": world.description,
            "events": world.events,
            "flags": world.flags,
        }
    }


@app.route("/api/worlds/<name>", methods=["DELETE"])
def delete_world(name: str) -> dict[str, str] | tuple[dict[str, str], int]:
    """Delete a world.

    Args:
        name: World name

    Returns:
        Success message, or error with 404 status
    """
    filepath = Path(config.WORLDS_DIR) / f"{name}.json"
    if not filepath.exists():
        return {"error": f"World '{name}' not found"}, 404

    filepath.unlink()
    return {"message": f"World '{name}' deleted"}


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id: str) -> dict[str, str] | tuple[dict[str, str], int]:
    """Delete a session.

    Args:
        session_id: Session ID

    Returns:
        Success message, or error with 404 status
    """
    filepath = Path(config.SESSION_DIR) / f"{session_id}.json"
    if not filepath.exists():
        return {"error": f"Session '{session_id}' not found"}, 404

    filepath.unlink()
    return {"message": f"Session '{session_id}' deleted"}


if __name__ == "__main__":
    port = int(config.API_PORT)
    print(f"Starting RP Engine API on http://localhost:{port}")
    print(f"LM Studio API: {config.LM_STUDIO_API_URL}")
    app.run(host="127.0.0.1", port=port, debug=False)

