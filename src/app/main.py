"""CLI entry point for rp-engine."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.config import config
from src.engine.orchestrator import Orchestrator
from src.llm.client import LMStudioClient
from src.memory.character import CharacterManager, CharacterState
from src.memory.session import SessionManager, SessionMemory
from src.memory.world import WorldManager, WorldState


def _setup_session(
    manager: SessionManager,
) -> SessionMemory:
    """Setup or load a session.

    Args:
        manager: SessionManager instance

    Returns:
        SessionMemory object
    """
    print("Session Setup")
    print("-" * 60)

    session_id = input("Session ID (or 'new' for new session): ").strip()
    if session_id.lower() == "new":
        session_id = input("Enter new session ID: ").strip()
        if not session_id:
            session_id = "default"

    # Load or create session
    session = None
    try:
        session = manager.load_session(session_id)
    except Exception as e:
        print(f"⚠️  Error loading session '{session_id}': {e}")
        create_new = input("Create new session instead? (y/n): ").strip().lower()
        if create_new != "y":
            print("Exiting...")
            sys.exit(0)

    if session is None:
        character_name = input("Character name: ").strip() or "NPC"
        world_name = input("World/Setting name (optional): ").strip() or None
        session = manager.create_session(
            session_id=session_id,
            character_name=character_name,
            world_name=world_name,
        )
        print(f"Created new session: {session_id}\n")
    else:
        print(f"Loaded session: {session_id}")
        print(f"  Character: {session.character_name}")
        print(f"  Messages: {session.message_count()}")
        print()

    return session


def _setup_character(
    character_name: str,
    manager: CharacterManager,
) -> CharacterState:
    """Setup or load a character.

    Args:
        character_name: Name of character
        manager: CharacterManager instance

    Returns:
        CharacterState object
    """
    character = manager.load_character(character_name)
    if character is None:
        personality = (
            input(f"Character personality for {character_name}: ").strip()
            or "Neutral"
        )
        tone = input("Character tone (optional): ").strip() or "Conversational"
        character = manager.create_character(
            name=character_name,
            personality=personality,
            tone=tone,
        )
        print()
    else:
        print(f"Loaded character: {character.name}")
        print(f"  Personality: {character.personality}")
        print()

    return character


def _setup_world(
    world_name: str | None,
    manager: WorldManager,
) -> WorldState:
    """Setup or load a world.

    Args:
        world_name: Name of world (optional)
        manager: WorldManager instance

    Returns:
        WorldState object
    """
    if not world_name:
        world_name = "Default World"

    world = manager.load_world(world_name)
    if world is None:
        description = (
            input(f"World description for {world_name} (optional): ").strip() or ""
        )
        world = manager.create_world(name=world_name, description=description)
        print()
    else:
        print(f"Loaded world: {world.name}")
        print()

    return world


def main() -> None:
    """Main CLI loop for the roleplay engine."""
    print("=" * 60)
    print("RP Engine - Local Roleplay with Persistent Memory")
    print("=" * 60)
    print()

    # Initialize managers
    session_manager = SessionManager(config.SESSION_DIR)
    character_manager = CharacterManager(config.CHARACTERS_DIR)
    world_manager = WorldManager(config.WORLDS_DIR)

    # Setup session, character, and world
    session = _setup_session(session_manager)
    character = _setup_character(session.character_name, character_manager)
    world = _setup_world(session.world_name, world_manager)

    # Initialize LLM client
    print("Initializing LM Studio client...")
    print(f"API URL: {config.LM_STUDIO_API_URL}")
    llm_client = LMStudioClient(config.LM_STUDIO_API_URL)

    # Initialize orchestrator
    orchestrator = Orchestrator(
        llm_client=llm_client,
        session=session,
        character=character,
        world=world,
        model="local-model",
    )

    # Print session info and start chat loop
    print("=" * 60)
    print(orchestrator.get_session_summary())
    print("=" * 60)
    print("Type 'exit' to quit, 'save' to save session, 'quit' to save and exit\n")

    try:
        while True:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() == "exit":
                print("Exiting without saving...")
                break

            if user_input.lower() in ("quit", "save"):
                session_manager.save_session(session)
                character_manager.save_character(character)
                if world:
                    world_manager.save_world(world)
                print("Session saved.")
                if user_input.lower() == "quit":
                    break
                continue

            # Process user input through orchestrator
            try:
                response = orchestrator.step(user_input)
                print(f"\n{response}\n")
            except Exception as e:
                print(f"\nError: {e}\n")
                continue

    except KeyboardInterrupt:
        print("\n\nInterrupted. Saving session...")
        session_manager.save_session(session)
        character_manager.save_character(character)
        if world:
            world_manager.save_world(world)
    finally:
        llm_client.close()
        print("Cleaned up. Goodbye!")


if __name__ == "__main__":
    main()

