import re
from uuid import UUID

from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.ports.character_store import CharacterStore
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.session_store import SessionStore
from rp_engine.core.ports.world_store import WorldStore
from rp_engine.core.session.session import Session, SessionOwnerKind


class CharacterService:
    def __init__(
        self,
        *,
        character_store: CharacterStore,
        conversation_store: ConversationStore,
        world_store: WorldStore,
        session_store: SessionStore,
        default_world_id: str,
    ) -> None:
        self._character_store = character_store
        self._conversation_store = conversation_store
        self._world_store = world_store
        self._session_store = session_store
        self._default_world_id = default_world_id

    async def select_character_for_user(
        self,
        *,
        user_id: UUID,
        command: SelectCharacterCommand,
    ) -> Session:
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
    ) -> Session:
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
    ) -> Session:
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
        world = await self._world_store.get_by_id(self._default_world_id)
        if world is None:
            world = await self._world_store.create_default(world_id=self._default_world_id)

        existing = await self._session_store.find_by_relationship(
            owner_kind=owner_kind,
            owner_id=owner_id,
            character_id=character.id,
            world_id=world.id,
        )
        if existing is not None:
            await self._session_store.set_active_for_owner(
                owner_kind=owner_kind,
                owner_id=owner_id,
                session_id=existing.id,
            )
            return existing

        if owner_kind == "user":
            session = Session.create_for_user(
                user_id=owner_id,
                character_id=character.id,
                world_id=world.id,
            )
        else:
            session = Session.create_for_group(
                group_id=owner_id,
                character_id=character.id,
                world_id=world.id,
            )
        saved = await self._session_store.save(session)
        await self._session_store.set_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=saved.id,
        )
        return saved

    async def ensure_active_session_for_user(self, *, user_id: UUID) -> Session:
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
    ) -> Session:
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
    ) -> Session:
        active = await self._session_store.get_active_for_owner(
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
        world = await self._world_store.get_by_id(self._default_world_id)
        if world is None:
            world = await self._world_store.create_default(world_id=self._default_world_id)

        if owner_kind == "user":
            session = Session.create_for_user(
                user_id=owner_id,
                character_id=default_character.id,
                world_id=world.id,
            )
        else:
            session = Session.create_for_group(
                group_id=owner_id,
                character_id=default_character.id,
                world_id=world.id,
            )
        saved = await self._session_store.save(session)
        await self._session_store.set_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=saved.id,
        )
        return saved

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

    async def describe_session_entry(self, *, session: Session) -> str | None:
        character = await self._character_store.get_by_id(session.character_id)
        if character is None:
            return None

        memory_key = ConversationIdentity.for_session(str(session.id)).to_memory_key()
        history = await self._conversation_store.load_messages(memory_key)
        greeting = character.greeting.strip()

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
            return "No resumable turns yet."

        recent = summary_source[-4:]
        return self._build_inferred_resume(recent)

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
