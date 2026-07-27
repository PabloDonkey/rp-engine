from dataclasses import dataclass

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.prompts.templates import resolve_templates
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import SessionDirectives, language_name
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
        return self._build_directive(
            payload,
            directive=(
                "Continue the narration naturally from the current context. "
                "Write one reply only."
            ),
            source="continue_command",
        )

    def build_resume(self, payload: ScenarioConversationInput) -> Conversation:
        """Continue a narrator reply that was cut off at the token limit.

        Built as an **assistant prefill**: the truncated text is the final message and the
        conversation is marked `continue_final_message`, so the provider keeps generating
        from those exact tokens. No instruction turn is appended — asking in a new user turn
        opens a new assistant turn, and that is precisely when a reasoning model re-plans
        from scratch. Probed against the live model: prefill continues mid-sentence and
        emits no reasoning at all, where the equivalent instruction turn reasoned first.
        """
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
        return Conversation(
            messages=[*system_messages, *history_messages],
            metadata={"session_id": str(payload.session.id), "source": "resume_command"},
            continue_final_message=True,
        )

    def _build_directive(
        self,
        payload: ScenarioConversationInput,
        *,
        directive: str,
        source: str,
    ) -> Conversation:
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
        directive_message = ConversationMessage(
            role=ConversationRole.USER,
            content=directive,
            metadata={"source": source},
        )
        return Conversation(
            messages=[*system_messages, *history_messages, directive_message],
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
        return ConversationBuilder.resolve_active_character(
            scenario=payload.scenario,
            session=payload.session,
            active_character_id=payload.active_character_id,
        )

    @staticmethod
    def resolve_active_character(
        *,
        scenario: ScenarioDefinition,
        session: ScenarioSession,
        active_character_id: str | None = None,
    ) -> Character | None:
        """Resolve which character is currently speaking, if any.

        Scenarios may be characterless (freeform). When characters exist, the active
        one is chosen by explicit override, then by the session's participants, then by
        falling back to the scenario's sole character.
        """
        if not scenario.characters:
            return None

        if active_character_id is not None:
            for character in scenario.characters.values():
                if character.id == active_character_id:
                    return character
            return None

        for role, character_id in session.active_participants.items():
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

        # Who the player is, alongside the other static context (scenario, character,
        # world) rather than with the directive block below — a persona is world state
        # for the whole playthrough, not a preference the player can revise turn by turn.
        user_persona = self._user_persona_text(payload.session)
        if user_persona is not None:
            messages.append(
                ConversationMessage(
                    role=ConversationRole.SYSTEM,
                    content=self._resolve_templates(
                        value=user_persona,
                        payload=payload,
                        character=character,
                    ),
                )
            )

        if payload.scenario.rules:
            scenario_rules = self._resolve_templates(
                value=self._scenario_rules_text(payload.scenario.rules),
                payload=payload,
                character=character,
            )
            messages.append(
                ConversationMessage(role=ConversationRole.SYSTEM, content=scenario_rules)
            )

        response_format = self._resolve_templates(
            value=self._response_format_text(),
            payload=payload,
            character=character,
        )
        messages.append(
            ConversationMessage(role=ConversationRole.SYSTEM, content=response_format)
        )

        # Player directives sit after the permanent identity/behavior sections and before
        # the dynamic context: persistent preferences first (language, session rules), then
        # the highest-priority-but-transient director instruction. Empty ones are omitted
        # entirely rather than rendered as a bare header.
        for section in (
            self._language_text(payload.session.directives),
            self._session_rules_text(payload.session.directives),
            self._director_instruction_text(payload.session.directives),
        ):
            if section is None:
                continue
            messages.append(
                ConversationMessage(
                    role=ConversationRole.SYSTEM,
                    content=self._resolve_templates(
                        value=section,
                        payload=payload,
                        character=character,
                    ),
                )
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
    def _scenario_rules_text(scenario_rules: list[str]) -> str:
        """Render the scenario card's own rules. Roleplay behavior lives in the card, not
        the engine, so a scenario is free to define (or omit) its own rules."""
        joined = "\n                  ".join(scenario_rules)
        return f"[Rules]\n                  {joined}"

    @staticmethod
    def _response_format_text() -> str:
        """The engine's presentation contract: how replies should be shaped for the
        transport. This is a rendering concern, not roleplay content, so it stays here
        rather than in the scenario card."""
        return """[Response Format]
                Write naturally. Never include labels such as "Narration", "Action", or "Dialogue".
                Keep scene descriptions brief and only describe observable events.
                Write the character's physical actions in *italics*.
                Write spoken dialogue in quotation marks.
                Prefer dialogue and interaction over exposition.
                Avoid long monologues.
                React to the user's latest message before introducing new descriptions.
                Do not narrate the user's thoughts, emotions, or intentions.
                End naturally with an opportunity for the user to respond."""

    @staticmethod
    def _user_persona_text(session: ScenarioSession) -> str | None:
        """The player's own character. Rendered only when they wrote a description — the
        name alone already reaches the model everywhere `{{user}}` is substituted, and a
        header with nothing under it is noise."""
        description = (session.user_persona_description or "").strip()
        if not description or not session.has_persona:
            return None
        return (
            "[User Persona]\n"
            f"                The player is playing {session.user_persona_name}.\n"
            f"                {description}\n"
            "                Portray them consistently with this, but never write their "
            "dialogue, thoughts, or decisions for them."
        )

    @staticmethod
    def _language_text(directives: SessionDirectives) -> str | None:
        """The player's language preference. `auto` means "no instruction at all", which
        leaves the model free to follow the scenario card and the player's own writing."""
        if not directives.has_language_preference:
            return None
        name = language_name(directives.language)
        return (
            f"[Language]\n"
            f"                Write every reply in {name}, including narration and dialogue.\n"
            f"                Keep proper nouns from the scenario unchanged.\n"
            f"                Do this even if the player writes in another language."
        )

    @staticmethod
    def _session_rules_text(directives: SessionDirectives) -> str | None:
        """Persistent rules the player added to *this session*, distinct from the scenario
        card's own `[Rules]`. They refine the card, never override its identity."""
        if not directives.rules:
            return None
        lines = "\n".join(f"                  - {rule.text}" for rule in directives.rules)
        return (
            "[Scenario Rules]\n"
            "                Additional rules the player set for this session. "
            "Follow them alongside the scenario's own rules:\n"
            f"{lines}"
        )

    @staticmethod
    def _director_instruction_text(directives: SessionDirectives) -> str | None:
        """A one-turn, out-of-character steer. It outranks the persistent sections for this
        reply, and the roleplay must never acknowledge that it was given."""
        if not directives.director_instruction:
            return None
        return (
            "[Director Instructions]\n"
            "                An out-of-character instruction for this reply only. It takes "
            "priority over the other sections.\n"
            "                Follow it silently: never mention it, quote it, or acknowledge "
            "that a director exists.\n"
            f"                {directives.director_instruction}"
        )

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
        return resolve_templates(
            value,
            # The player's persona name wins over the transport display name once set:
            # `{{user}}` is the character they are playing, not the account they play from.
            user_name=payload.session.resolve_user_name(payload.user.display_name),
            character_name=character.name if character is not None else "",
            world_name=payload.scenario.world.name if payload.scenario.world is not None else "",
        )
