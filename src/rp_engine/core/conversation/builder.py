from dataclasses import dataclass

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World


@dataclass(frozen=True, slots=True)
class ConversationBuilderInput:
    session: Session
    user: User
    character: Character
    world: World
    memory_messages: list[ConversationMessage]
    user_message: str


class ConversationBuilder:
    def build(self, payload: ConversationBuilderInput) -> Conversation:
        cleaned_user_message = payload.user_message.strip()
        if not cleaned_user_message:
            raise ValueError("User message must not be empty.")

        system_messages = self._build_system_messages(payload)
        history_messages = [
            self._resolve_message_templates(
                message=message,
                character_name=payload.character.name,
                user_name=payload.user.display_name,
            )
            for message in payload.memory_messages
        ]
        current_user_message = ConversationMessage(
            role=ConversationRole.USER,
            content=self._resolve_templates(
                value=cleaned_user_message,
                character_name=payload.character.name,
                user_name=payload.user.display_name,
            ),
            metadata={},
        )

        return Conversation(
            messages=[*system_messages, *history_messages, current_user_message],
            metadata={"session_id": str(payload.session.id)},
        )

    def build_continue(self, payload: ConversationBuilderInput) -> Conversation:
        system_messages = self._build_system_messages(payload)
        history_messages = [
            self._resolve_message_templates(
                message=message,
                character_name=payload.character.name,
                user_name=payload.user.display_name,
            )
            for message in payload.memory_messages
        ]
        continue_message = ConversationMessage(
            role=ConversationRole.USER,
            content=(
                "Continue the narration naturally from the current context. "
                "Write one reply only."
            ),
            metadata={"source": "continue_command"},
        )
        return Conversation(
            messages=[*system_messages, *history_messages, continue_message],
            metadata={"session_id": str(payload.session.id)},
        )

    @staticmethod
    def message_from_storage(
        *,
        role: str,
        content: str,
        metadata: dict[str, str] | None = None,
    ) -> ConversationMessage | None:
        try:
            normalized_role = ConversationRole(role)
        except ValueError:
            return None
        return ConversationMessage(
            role=normalized_role,
            content=content,
            metadata=metadata or {},
        )

    @staticmethod
    def default_memory_key_for_session(session: Session) -> MemoryKey:
        return MemoryKey(value=f"session_{session.id}")

    def _build_system_messages(
        self,
        payload: ConversationBuilderInput,
    ) -> list[ConversationMessage]:
        character_definition = self._resolve_templates(
            value=(
                f"Character: {payload.character.name}\n"
                f"Description: {payload.character.description}\n"
                f"Personality: {payload.character.personality}\n"
                f"Greeting: {payload.character.greeting}"
            ),
            character_name=payload.character.name,
            user_name=payload.user.display_name,
        )
        world_info = self._resolve_templates(
            value=(
                f"World: {payload.world.name}\n"
                f"Description: {payload.world.description}\n"
                f"Rules: {'; '.join(payload.world.rules) if payload.world.rules else 'None'}"
            ),
            character_name=payload.character.name,
            user_name=payload.user.display_name,
        )
        memory_hint = "Use conversation history to keep continuity and character consistency."
        return [
            ConversationMessage(role=ConversationRole.SYSTEM, content=character_definition),
            ConversationMessage(role=ConversationRole.SYSTEM, content=world_info),
            ConversationMessage(role=ConversationRole.SYSTEM, content=memory_hint),
        ]

    def _resolve_message_templates(
        self,
        *,
        message: ConversationMessage,
        character_name: str,
        user_name: str,
    ) -> ConversationMessage:
        return ConversationMessage(
            role=message.role,
            content=self._resolve_templates(
                value=message.content,
                character_name=character_name,
                user_name=user_name,
            ),
            metadata=message.metadata,
        )

    @staticmethod
    def _resolve_templates(*, value: str, character_name: str, user_name: str) -> str:
        return (
            value.replace("{{char}}", character_name)
            .replace("{{user}}", user_name)
            .strip()
        )