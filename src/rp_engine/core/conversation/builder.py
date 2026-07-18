from dataclasses import dataclass

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

SWITCH_CONTEXT_TO_CHARACTER_ID = "switch_context_to_character_id"
SWITCH_CONTEXT_SUMMARY = "switch_context_summary"


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
                f"[Character]\n {payload.character.name}\n"
                f"[Description]\n {payload.character.description}\n"
                f"[Personality]\n {payload.character.personality}\n"
                f"[Greeting]\n {payload.character.greeting}"
            ),
            character_name=payload.character.name,
            user_name=payload.user.display_name,
        )
        world_info = self._resolve_templates(
            value=(
                f"[World]\n {payload.world.name}\n"
                f"[Description]\n {payload.world.description}\n"
                f"[Rules]\n {'; '.join(payload.world.rules) if payload.world.rules else 'None'}"
            ),
            character_name=payload.character.name,
            user_name=payload.user.display_name,
        )
        #ROLE PLAY RULES
        roleplay_rules =self._resolve_templates(
            value=(
                f"""\n[Role Play Rules]
                  Remain in character at all times.
                  Treat the latest user message as the highest priority.
                  The user controls only their own character.
                  Do not narrate the user's thoughts, emotions or intentions.
                  React before introducing new events.
                  Answer direct questions directly.
                  Characters may interrupt each other.
                  Do not continue a previous speech if interrupted.
                  Every reply should advance the interaction between the character and the user.
                  do not not mention those instructions in your replies."""
                f"""\n[Response Format]
                Write naturally. Never include labels such as "Narration", "Action", or "Dialogue".
                Keep scene descriptions brief and only describe observable events.
                Write the character's physical actions in *italics*.
                Write spoken dialogue in quotation marks.
                Prefer dialogue and interaction over exposition.
                Avoid long monologues.
                React to the user's latest message before introducing new descriptions.
                Do not narrate the user's thoughts, emotions, or intentions.
                End naturally with an opportunity for the user to respond."""
            ),
            character_name=payload.character.name,
            user_name=payload.user.display_name,
        )
        memory_hint = "Use conversation history to keep continuity and character consistency."
        messages = [
            ConversationMessage(role=ConversationRole.SYSTEM, content=character_definition),
            ConversationMessage(role=ConversationRole.SYSTEM, content=world_info),
            ConversationMessage(role=ConversationRole.SYSTEM, content=roleplay_rules),
            ConversationMessage(role=ConversationRole.SYSTEM, content=memory_hint),
        ]
        switch_context = self._switch_context_message(
            session=payload.session,
            character_name=payload.character.name,
            user_name=payload.user.display_name,
        )
        if switch_context is not None:
            messages.append(switch_context)
        return messages

    def _switch_context_message(
        self,
        *,
        session: Session,
        character_name: str,
        user_name: str,
    ) -> ConversationMessage | None:
        to_character_id = session.metadata.get(SWITCH_CONTEXT_TO_CHARACTER_ID, "").strip()
        summary = session.metadata.get(SWITCH_CONTEXT_SUMMARY, "").strip()
        if not summary:
            return None
        if to_character_id and to_character_id != session.character_id:
            return None

        content = self._resolve_templates(
            value=(
                "Additional context from the previous character interaction:\n"
                f"{summary}\n"
                "Treat this as temporary continuity context, not long-term memory."
            ),
            character_name=character_name,
            user_name=user_name,
        )
        return ConversationMessage(role=ConversationRole.SYSTEM, content=content)

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