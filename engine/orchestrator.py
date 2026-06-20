"""Main orchestration engine for roleplay interactions."""

from typing import Optional

from llm.client import LMStudioClient
from engine.prompt_builder import PromptBuilder
from memory.session import SessionMemory
from memory.character import CharacterState
from memory.world import WorldState


class Orchestrator:
    """Orchestrates interactions between session, character, world, and LLM."""

    def __init__(
        self,
        llm_client: LMStudioClient,
        session: SessionMemory,
        character: Optional[CharacterState] = None,
        world: Optional[WorldState] = None,
        model: str = "local-model",
    ) -> None:
        """Initialize the orchestrator.

        Args:
            llm_client: Initialized LM Studio client
            session: Session memory to manage
            character: Optional character state
            world: Optional world state
            model: Model name to use for LLM calls
        """
        self.llm_client = llm_client
        self.session = session
        self.character = character
        self.world = world
        self.model = model
        self.prompt_builder = PromptBuilder(character=character, world=world)

    def step(self, user_input: str) -> str:
        """Process a single user input and get a response.

        Args:
            user_input: User's input text

        Returns:
            Model response

        Raises:
            requests.RequestException: If LLM API call fails
        """
        # Add user message to session
        self.session.add_message("user", user_input)

        # Build messages for API call
        messages = self.prompt_builder.build_messages(
            self.session,
            user_input,
            context_messages=10,
        )

        # Get response from LLM
        response = self.llm_client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )

        # Add assistant response to session
        self.session.add_message("assistant", response)

        return response

    def get_session_summary(self) -> str:
        """Get a summary of the current session.

        Returns:
            Session summary string
        """
        summary_parts = [
            f"Session: {self.session.session_id}",
            f"Character: {self.session.character_name}",
            f"Messages: {self.session.message_count()}",
        ]

        if self.session.world_name:
            summary_parts.append(f"World: {self.session.world_name}")

        return " | ".join(summary_parts)