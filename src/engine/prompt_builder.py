"""Prompt building and orchestration."""

from typing import Optional

from src.llm.client import ChatMessage
from src.memory.session import SessionMemory
from src.memory.character import CharacterState
from src.memory.world import WorldState


class PromptBuilder:
    """Builds structured prompts for the LLM."""

    def __init__(
        self,
        character: Optional[CharacterState] = None,
        world: Optional[WorldState] = None,
    ) -> None:
        """Initialize prompt builder.

        Args:
            character: Character state to inject into prompts
            world: World state to inject into prompts
        """
        self.character = character
        self.world = world

    def build_system_prompt(self) -> str:
        """Build the system prompt.

        Returns:
            System prompt string
        """
        parts: list[str] = []

        # Character system prompt
        if self.character:
            parts.append(f"You are {self.character.name}.")
            if self.character.personality:
                parts.append(f"Personality: {self.character.personality}")
            if self.character.tone:
                parts.append(f"Tone: {self.character.tone}")
            if self.character.notes:
                parts.append(f"Notes: {self.character.notes}")

        # World context
        if self.world:
            parts.append(f"\nWorld: {self.world.name}")
            if self.world.description:
                parts.append(f"Description: {self.world.description}")
            if self.world.current_location:
                parts.append(f"Location: {self.world.current_location}")

        if not parts:
            return "You are a helpful roleplay assistant."

        return "\n".join(parts)

    def build_messages(
        self,
        session: SessionMemory,
        user_input: str,
        context_messages: int = 10,
    ) -> list[ChatMessage]:
        """Build complete message list for API call.

        Args:
            session: Session memory to draw from
            user_input: Current user input
            context_messages: Number of previous messages to include

        Returns:
            List of ChatMessage objects ready for API
        """
        messages: list[ChatMessage] = []

        # System message
        system_prompt = self.build_system_prompt()
        messages.append(ChatMessage(role="system", content=system_prompt))

        # Include previous context messages
        recent_messages = session.get_last_n_messages(context_messages)
        for msg in recent_messages:
            messages.append(
                ChatMessage(role=msg.role, content=msg.content)
            )

        # Current user input
        messages.append(ChatMessage(role="user", content=user_input))

        return messages

    def build_prompt_text(
        self,
        session: SessionMemory,
        user_input: str,
        context_messages: int = 10,
    ) -> str:
        """Build a complete prompt as a single string (for debugging).

        Args:
            session: Session memory to draw from
            user_input: Current user input
            context_messages: Number of previous messages to include

        Returns:
            Complete prompt as string
        """
        parts: list[str] = []

        # System prompt
        parts.append("=== SYSTEM PROMPT ===")
        parts.append(self.build_system_prompt())
        parts.append("")

        # Context
        parts.append("=== CONTEXT ===")
        recent_messages = session.get_last_n_messages(context_messages)
        for msg in recent_messages:
            parts.append(f"{msg.role.upper()}: {msg.content}")
        parts.append("")

        # Current input
        parts.append("=== CURRENT INPUT ===")
        parts.append(f"USER: {user_input}")

        return "\n".join(parts)