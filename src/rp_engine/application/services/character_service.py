import logging
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.ports.character_store import CharacterStore
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.conversation_summarizer import ConversationSummarizer
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.ports.world_store import WorldStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind
from rp_engine.core.world.world import World

logger = logging.getLogger(__name__)

SWITCH_CONTEXT_FROM_CHARACTER_ID = "switch_context_from_character_id"
SWITCH_CONTEXT_TO_CHARACTER_ID = "switch_context_to_character_id"
SWITCH_CONTEXT_SUMMARY = "switch_context_summary"
SWITCH_CONTEXT_CREATED_AT = "switch_context_created_at"

# Role key used for the auto-derived single-character scenario a character selection
# produces. Multi-character scenarios (future) will use richer role maps.
AUTO_ROLE = "character"

SelectionStatus = Literal["activated", "switched", "already_active"]


@dataclass(frozen=True, slots=True)
class CharacterSelectionResult:
    session: ScenarioSession
    character_id: str
    world_id: str
    status: SelectionStatus


class CharacterService:
    def __init__(
        self,
        *,
        character_store: CharacterStore,
        conversation_store: ConversationStore,
        conversation_summarizer: ConversationSummarizer,
        world_store: WorldStore,
        scenario_definition_store: ScenarioDefinitionStore,
        scenario_session_store: ScenarioSessionStore,
        default_world_id: str,
    ) -> None:
        self._character_store = character_store
        self._conversation_store = conversation_store
        self._conversation_summarizer = conversation_summarizer
        self._world_store = world_store
        self._scenario_definition_store = scenario_definition_store
        self._scenario_session_store = scenario_session_store
        self._default_world_id = default_world_id

    async def select_character_for_user(
        self,
        *,
        user_id: UUID,
        command: SelectCharacterCommand,
    ) -> CharacterSelectionResult:
        return await self._select_character(
            owner_kind="user",
            owner_id=user_id,
            character_owner_id=user_id,
            command=command,
        )

    async def select_character_for_group(
        self,
        *,
        group_id: UUID,
        actor_user_id: UUID,
        command: SelectCharacterCommand,
    ) -> CharacterSelectionResult:
        return await self._select_character(
            owner_kind="group",
            owner_id=group_id,
            character_owner_id=actor_user_id,
            command=command,
        )

    async def _select_character(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        character_owner_id: UUID,
        command: SelectCharacterCommand,
    ) -> CharacterSelectionResult:
        raw_name = command.character_name.strip()
        if not raw_name:
            raise ValueError("Character name must not be empty.")

        slug = self._slugify(raw_name)
        if not slug:
            raise ValueError("Character name must contain letters or numbers.")

        character = await self._resolve_existing_character(
            raw_name=raw_name,
            slug=slug,
            owner_id=character_owner_id,
        )
        world = await self._resolve_default_world()
        definition = await self._ensure_single_character_scenario(
            owner_id=owner_id,
            character=character,
            world=world,
        )

        active = await self._scenario_session_store.get_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
        )
        if active is not None and active.scenario_definition_id == definition.id:
            return self._result(active, character.id, world.id, "already_active")

        switch_summary = await self._build_switch_summary(
            active_session=active,
            next_character_id=character.id,
        )
        from_character_id = self._active_character_id(active) if active is not None else None

        existing = await self._scenario_session_store.find_by_definition(
            owner_kind=owner_kind,
            owner_id=owner_id,
            scenario_definition_id=definition.id,
        )
        status: SelectionStatus = "switched" if active is not None else "activated"

        if existing is not None:
            session = self._apply_switch_context(
                session=existing,
                from_character_id=from_character_id,
                to_character_id=character.id,
                summary=switch_summary,
            )
        else:
            session = self._new_session(
                owner_kind=owner_kind,
                owner_id=owner_id,
                definition=definition,
                character=character,
            )
            session = self._apply_switch_context(
                session=session,
                from_character_id=from_character_id,
                to_character_id=character.id,
                summary=switch_summary,
            )

        saved = await self._scenario_session_store.save(session)
        await self._scenario_session_store.set_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=saved.id,
        )
        return self._result(saved, character.id, world.id, status)

    async def ensure_active_session_for_user(self, *, user_id: UUID) -> ScenarioSession:
        return await self._ensure_active_session(
            owner_kind="user",
            owner_id=user_id,
            character_owner_id=user_id,
        )

    async def ensure_active_session_for_group(
        self,
        *,
        group_id: UUID,
        actor_user_id: UUID,
    ) -> ScenarioSession:
        return await self._ensure_active_session(
            owner_kind="group",
            owner_id=group_id,
            character_owner_id=actor_user_id,
        )

    async def _ensure_active_session(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        character_owner_id: UUID,
    ) -> ScenarioSession:
        active = await self._scenario_session_store.get_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
        )
        if active is not None:
            return active

        # Create the default roleplay context for first-time users.
        default_character = await self._resolve_or_create_character(
            raw_name="Default Character",
            slug="default",
            owner_id=character_owner_id,
            visibility=CharacterVisibility.PUBLIC,
        )
        world = await self._resolve_default_world()
        definition = await self._ensure_single_character_scenario(
            owner_id=owner_id,
            character=default_character,
            world=world,
        )

        existing = await self._scenario_session_store.find_by_definition(
            owner_kind=owner_kind,
            owner_id=owner_id,
            scenario_definition_id=definition.id,
        )
        session = existing or self._new_session(
            owner_kind=owner_kind,
            owner_id=owner_id,
            definition=definition,
            character=default_character,
        )
        saved = await self._scenario_session_store.save(session)
        await self._scenario_session_store.set_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=saved.id,
        )
        return saved

    async def describe_session_entry(self, *, session: ScenarioSession) -> str | None:
        character_id = self._active_character_id(session)
        if character_id is None:
            return None
        character = await self._character_store.get_by_id(character_id)
        if character is None:
            return None

        memory_key = ConversationIdentity.for_session(str(session.id)).to_memory_key()
        history = await self._conversation_store.load_messages(memory_key)
        greeting = self._resolve_entry_greeting(character).strip()

        if not history:
            if not greeting:
                return None

            await self._conversation_store.save_message(
                memory_key,
                ConversationMessage(role=ConversationRole.CHARACTER, content=greeting),
            )
            return greeting

        summary_source = history
        if (
            greeting
            and summary_source
            and summary_source[0].role == ConversationRole.CHARACTER
            and summary_source[0].content.strip() == greeting
        ):
            summary_source = summary_source[1:]

        if not summary_source:
            if greeting:
                return greeting
            return "No resumable turns yet."

        recent = summary_source[-4:]
        return self._build_inferred_resume(recent)

    async def _resolve_default_world(self) -> World:
        world = await self._world_store.get_by_id(self._default_world_id)
        if world is None:
            world = await self._world_store.create_default(world_id=self._default_world_id)
        return world

    async def _ensure_single_character_scenario(
        self,
        *,
        owner_id: UUID,
        character: Character,
        world: World,
    ) -> ScenarioDefinition:
        """Upsert the auto-derived single-character scenario for a selection.

        The definition is refreshed on every selection so character/world edits are
        reflected the next time the character is chosen.
        """
        definition = ScenarioDefinition.create(
            scenario_id=f"auto-{owner_id}-{character.id}-{world.id}",
            owner_id=owner_id,
            name=character.name,
            description="",
            world=world,
            characters={AUTO_ROLE: character},
        )
        await self._scenario_definition_store.save(definition)
        return definition

    @staticmethod
    def _new_session(
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        definition: ScenarioDefinition,
        character: Character,
    ) -> ScenarioSession:
        participants = {AUTO_ROLE: character.id}
        if owner_kind == "user":
            return ScenarioSession.create_for_user(
                scenario_definition_id=definition.id,
                user_id=owner_id,
                active_participants=participants,
            )
        return ScenarioSession.create_for_group(
            scenario_definition_id=definition.id,
            group_id=owner_id,
            active_participants=participants,
        )

    @staticmethod
    def _result(
        session: ScenarioSession,
        character_id: str,
        world_id: str,
        status: SelectionStatus,
    ) -> CharacterSelectionResult:
        return CharacterSelectionResult(
            session=session,
            character_id=character_id,
            world_id=world_id,
            status=status,
        )

    @staticmethod
    def _active_character_id(session: ScenarioSession) -> str | None:
        for character_id in session.active_participants.values():
            return character_id
        return None

    async def _resolve_existing_character(
        self,
        *,
        raw_name: str,
        slug: str,
        owner_id: UUID,
    ) -> Character:
        existing = await self._character_store.get_by_id(slug)
        if existing is not None:
            self._assert_character_access(character=existing, actor_user_id=owner_id)
            return existing

        by_name = await self._character_store.find_by_name(raw_name)
        if by_name is not None:
            self._assert_character_access(character=by_name, actor_user_id=owner_id)
            return by_name

        raise ValueError("Character not found. Use /character create to create one first.")

    async def _resolve_or_create_character(
        self,
        *,
        raw_name: str,
        slug: str,
        owner_id: UUID,
        visibility: CharacterVisibility,
    ) -> Character:
        existing = await self._character_store.get_by_id(slug)
        if existing is not None:
            self._assert_character_access(character=existing, actor_user_id=owner_id)
            return existing

        by_name = await self._character_store.find_by_name(raw_name)
        if by_name is not None:
            self._assert_character_access(character=by_name, actor_user_id=owner_id)
            return by_name

        return await self._character_store.create_minimal(
            character_id=slug,
            owner_id=owner_id,
            name=raw_name,
            visibility=visibility,
        )

    @staticmethod
    def _assert_character_access(*, character: Character, actor_user_id: UUID) -> None:
        if (
            character.visibility == CharacterVisibility.PRIVATE
            and character.owner_id != actor_user_id
        ):
            raise ValueError("Character is private and belongs to another user.")

    @staticmethod
    def _slugify(value: str) -> str:
        lowered = value.lower().strip()
        replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
        return replaced.strip("-")

    @staticmethod
    def _label_for_role(role: ConversationRole) -> str:
        if role == ConversationRole.USER:
            return "User"
        if role == ConversationRole.CHARACTER:
            return "Character"
        return "System"

    @classmethod
    def _build_inferred_resume(cls, messages: list[ConversationMessage]) -> str:
        user_signals = [
            cls._truncate(message.content, limit=80)
            for message in messages
            if message.role == ConversationRole.USER
        ]
        character_signals = [
            cls._truncate(message.content, limit=80)
            for message in messages
            if message.role == ConversationRole.CHARACTER
        ]

        parts: list[str] = ["Inferred resume from recent turns:"]
        if user_signals:
            parts.append("- User intent recently focused on: " + "; ".join(user_signals[-2:]))
        if character_signals:
            parts.append(
                "- Character recently established: "
                + "; ".join(character_signals[-2:])
            )

        if len(parts) == 1:
            parts.append("- Recent context exists but does not include user/character turns.")

        return "\n".join(parts)

    @staticmethod
    def _truncate(value: str, limit: int = 160) -> str:
        trimmed = value.strip()
        if len(trimmed) <= limit:
            return trimmed
        return trimmed[: limit - 3].rstrip() + "..."

    @staticmethod
    def _resolve_entry_greeting(character: Character) -> str:
        greeting = character.greeting.strip()
        if greeting:
            return greeting
        return character.metadata.get("first_message", "").strip()

    async def _build_switch_summary(
        self,
        *,
        active_session: ScenarioSession | None,
        next_character_id: str,
    ) -> str | None:
        if active_session is None:
            return None
        active_character_id = self._active_character_id(active_session)
        if active_character_id == next_character_id:
            return None

        memory_key = ConversationIdentity.for_session(str(active_session.id)).to_memory_key()
        history = await self._conversation_store.load_messages(memory_key)
        recent_messages = history[-4:]
        if not recent_messages:
            return None

        try:
            summary = await self._conversation_summarizer.summarize_recent_conversation(
                recent_messages=recent_messages
            )
        except Exception:
            logger.exception(
                "Failed to generate character switch summary",
                extra={
                    "from_character_id": active_character_id,
                    "to_character_id": next_character_id,
                    "session_id": str(active_session.id),
                },
            )
            return None

        cleaned = summary.strip()
        if not cleaned:
            return None
        return cleaned

    @staticmethod
    def _apply_switch_context(
        *,
        session: ScenarioSession,
        from_character_id: str | None,
        to_character_id: str,
        summary: str | None,
    ) -> ScenarioSession:
        metadata = dict(session.metadata)
        metadata.pop(SWITCH_CONTEXT_FROM_CHARACTER_ID, None)
        metadata.pop(SWITCH_CONTEXT_TO_CHARACTER_ID, None)
        metadata.pop(SWITCH_CONTEXT_SUMMARY, None)
        metadata.pop(SWITCH_CONTEXT_CREATED_AT, None)

        if (
            summary is not None
            and from_character_id is not None
            and from_character_id != to_character_id
        ):
            metadata[SWITCH_CONTEXT_FROM_CHARACTER_ID] = from_character_id
            metadata[SWITCH_CONTEXT_TO_CHARACTER_ID] = to_character_id
            metadata[SWITCH_CONTEXT_SUMMARY] = summary
            metadata[SWITCH_CONTEXT_CREATED_AT] = datetime.now(UTC).isoformat()

        return replace(session, metadata=metadata)
