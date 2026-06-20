"""CLI entry point for rp-engine."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from engine.orchestrator import Orchestrator
from llm.client import LMStudioClient
from memory.session import SessionManager
from memory.character import CharacterManager
from memory.world import WorldManager


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

    # Get or create session
    print("Session Setup")
    print("-" * 60)

    session_id = input("Session ID (or 'new' for new session): ").strip()
    if session_id.lower() == "new":
        session_id = input("Enter new session ID: ").strip()
        if not session_id:
            session_id = "default"

    # Load or create session
    session = session_manager.load_session(session_id)
    if session is None:
        character_name = input("Character name: ").strip() or "NPC"
        world_name = input("World/Setting name (optional): ").strip() or None
        session = session_manager.create_session(
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

    # Load or create character
    character = character_manager.load_character(session.character_name)
    if character is None:
        personality = (
            input(f"Character personality for {session.character_name}: ").strip()
            or "Neutral"
        )
        tone = input("Character tone (optional): ").strip() or "Conversational"
        character = character_manager.create_character(
            name=session.character_name,
            personality=personality,
            tone=tone,
        )
        print()
    else:
        print(f"Loaded character: {character.name}")
        print(f"  Personality: {character.personality}")
        print(f"  Tone: {character.tone}")
        print()

    # Load or create world
    world = None
    if session.world_name:
        world = world_manager.load_world(session.world_name)
        if world is None:
            world_desc = (
                input(f"Description for world '{session.world_name}': ").strip()
                or ""
            )
            world = world_manager.create_world(
                name=session.world_name,
                description=world_desc,
            )
            print()

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