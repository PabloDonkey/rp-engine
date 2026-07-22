from dataclasses import dataclass

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User

# Session metadata keys used to carry short-lived continuity context when the active
# character changes. Written by the character switching flow, read here.
SWITCH_CONTEXT_TO_CHARACTER_ID = "switch_context_to_character_id"
SWITCH_CONTEXT_SUMMARY = "switch_context_summary"


@dataclass(frozen=True, slots=True)
class ScenarioConversationInput:
    """Input context for building a provider-independent conversation from a scenario."""

    scenario: ScenarioDefinition
    session: ScenarioSession
    user: User
    memory_messages: list[ConversationMessage]
    user_message: str
    # Optional explicit active character override; when absent the active character is
    # resolved from the session's participants (or the scenario's single character).
    active_character_id: str | None = None


class ConversationBuilder:
    def build(self, payload: ScenarioConversationInput) -> Conversation:
        cleaned_user_message = payload.user_message.strip()
        if not cleaned_user_message:
            raise ValueError("User message must not be empty.")

        character = self._resolve_active_character(payload)
        system_messages = self._build_system_messages(payload, character)
        history_messages = [
            self._resolve_message_templates(
                message=message,
                payload=payload,
                character=character,
            )
            for message in payload.memory_messages
        ]
        current_user_message = ConversationMessage(
            role=ConversationRole.USER,
            content=self._resolve_templates(
                value=cleaned_user_message,
                payload=payload,
                character=character,
            ),
            metadata={},
        )

        return Conversation(
            messages=[*system_messages, *history_messages, current_user_message],
            metadata={"session_id": str(payload.session.id)},
        )

    def build_continue(self, payload: ScenarioConversationInput) -> Conversation:
        character = self._resolve_active_character(payload)
        system_messages = self._build_system_messages(payload, character)
        history_messages = [
            self._resolve_message_templates(
                message=message,
                payload=payload,
                character=character,
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
    def default_memory_key_for_session(session: ScenarioSession) -> MemoryKey:
        return MemoryKey(value=f"session_{session.id}")

    @staticmethod
    def _resolve_active_character(payload: ScenarioConversationInput) -> Character | None:
        """Resolve which character is currently speaking, if any.

        Scenarios may be characterless (freeform). When characters exist, the active
        one is chosen by explicit override, then by the session's participants, then by
        falling back to the scenario's sole character.
        """
        scenario = payload.scenario
        if not scenario.characters:
            return None

        if payload.active_character_id is not None:
            for character in scenario.characters.values():
                if character.id == payload.active_character_id:
                    return character
            return None

        for role, character_id in payload.session.active_participants.items():
            if role in scenario.characters:
                return scenario.characters[role]
            for character in scenario.characters.values():
                if character.id == character_id:
                    return character

        if len(scenario.characters) == 1:
            return next(iter(scenario.characters.values()))
        return None

    def _build_system_messages(
        self,
        payload: ScenarioConversationInput,
        character: Character | None,
    ) -> list[ConversationMessage]:
        messages: list[ConversationMessage] = []

        scenario_intro = self._build_scenario_intro(payload)
        if scenario_intro is not None:
            messages.append(scenario_intro)

        if character is not None:
            character_definition = self._resolve_templates(
                value=(
                    f"[Character]\n {character.name}\n"
                    f"[Description]\n {character.description}\n"
                    f"[Personality]\n {character.personality}\n"
                    f"[Greeting]\n {character.greeting}"
                ),
                payload=payload,
                character=character,
            )
            messages.append(
                ConversationMessage(role=ConversationRole.SYSTEM, content=character_definition)
            )

        world = payload.scenario.world
        if world is not None:
            world_info = self._resolve_templates(
                value=(
                    f"[World]\n {world.name}\n"
                    f"[Description]\n {world.description}\n"
                    f"[Rules]\n {'; '.join(world.rules) if world.rules else 'None'}"
                ),
                payload=payload,
                character=character,
            )
            messages.append(
                ConversationMessage(role=ConversationRole.SYSTEM, content=world_info)
            )

        roleplay_rules = self._resolve_templates(
            value=self._roleplay_rules_text(payload.scenario.rules),
            payload=payload,
            character=character,
        )
        messages.append(
            ConversationMessage(role=ConversationRole.SYSTEM, content=roleplay_rules)
        )

        memory_hint = "Use conversation history to keep continuity and character consistency."
        messages.append(ConversationMessage(role=ConversationRole.SYSTEM, content=memory_hint))

        switch_context = self._switch_context_message(payload, character)
        if switch_context is not None:
            messages.append(switch_context)

        return messages

    def _build_scenario_intro(
        self,
        payload: ScenarioConversationInput,
    ) -> ConversationMessage | None:
        scenario = payload.scenario
        sections: list[str] = [f"[Scenario]\n {scenario.name}"]
        if scenario.description:
            sections.append(f"[Overview]\n {scenario.description}")
        if scenario.initial_context:
            sections.append(f"[Initial Context]\n {scenario.initial_context}")
        # Only emit an intro when it carries more than just the name.
        if len(sections) == 1:
            return None
        content = self._resolve_templates(
            value="\n".join(sections),
            payload=payload,
            character=None,
        )
        return ConversationMessage(role=ConversationRole.SYSTEM, content=content)

    @staticmethod
    def _roleplay_rules_text(scenario_rules: list[str]) -> str:
        base = (
            """\n[Role Play Rules]
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
            """\n[Response Format]
                Write naturally. Never include labels such as "Narration", "Action", or "Dialogue".
                Keep scene descriptions brief and only describe observable events.
                Write the character's physical actions in *italics*.
                Write spoken dialogue in quotation marks.
                Prefer dialogue and interaction over exposition.
                Avoid long monologues.
                React to the user's latest message before introducing new descriptions.
                Do not narrate the user's thoughts, emotions, or intentions.
                End naturally with an opportunity for the user to respond."""
        )
        if scenario_rules:
            joined = "\n                  ".join(scenario_rules)
            base += f"\n[Scenario Rules]\n                  {joined}"
        return base

    def _switch_context_message(
        self,
        payload: ScenarioConversationInput,
        character: Character | None,
    ) -> ConversationMessage | None:
        metadata = payload.session.metadata
        to_character_id = metadata.get(SWITCH_CONTEXT_TO_CHARACTER_ID, "").strip()
        summary = metadata.get(SWITCH_CONTEXT_SUMMARY, "").strip()
        if not summary:
            return None
        active_character_id = character.id if character is not None else ""
        if to_character_id and to_character_id != active_character_id:
            return None

        content = self._resolve_templates(
            value=(
                "Additional context from the previous character interaction:\n"
                f"{summary}\n"
                "Treat this as temporary continuity context, not long-term memory."
            ),
            payload=payload,
            character=character,
        )
        return ConversationMessage(role=ConversationRole.SYSTEM, content=content)

    def _resolve_message_templates(
        self,
        *,
        message: ConversationMessage,
        payload: ScenarioConversationInput,
        character: Character | None,
    ) -> ConversationMessage:
        return ConversationMessage(
            role=message.role,
            content=self._resolve_templates(
                value=message.content,
                payload=payload,
                character=character,
            ),
            metadata=message.metadata,
        )

    @staticmethod
    def _resolve_templates(
        *,
        value: str,
        payload: ScenarioConversationInput,
        character: Character | None,
    ) -> str:
        character_name = character.name if character is not None else "the character"
        world_name = payload.scenario.world.name if payload.scenario.world is not None else ""
        return (
            value.replace("{{char}}", character_name)
            .replace("{{user}}", payload.user.display_name)
            .replace("{{world}}", world_name)
            .strip()
        )
