import re
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.ports.character_store import CharacterStore
from rp_engine.core.ports.session_store import SessionStore
from rp_engine.core.ports.world_store import WorldStore
from rp_engine.core.services.commands import SelectCharacterCommand
from rp_engine.core.session.session import Session, SessionOwnerKind


class CharacterService:
    def __init__(
        self,
        *,
        character_store: CharacterStore,
        world_store: WorldStore,
        session_store: SessionStore,
        default_world_id: str,
    ) -> None:
        self._character_store = character_store
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
            command=command,
        )

    async def select_character_for_group(
        self,
        *,
        group_id: UUID,
        command: SelectCharacterCommand,
    ) -> Session:
        return await self._select_character(
            owner_kind="group",
            owner_id=group_id,
            command=command,
        )

    async def _select_character(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        command: SelectCharacterCommand,
    ) -> Session:
        raw_name = command.character_name.strip()
        if not raw_name:
            raise ValueError("Character name must not be empty.")

        slug = self._slugify(raw_name)
        if not slug:
            raise ValueError("Character name must contain letters or numbers.")

        character = await self._resolve_or_create_character(raw_name=raw_name, slug=slug)
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
        return await self._ensure_active_session(owner_kind="user", owner_id=user_id)

    async def ensure_active_session_for_group(self, *, group_id: UUID) -> Session:
        return await self._ensure_active_session(owner_kind="group", owner_id=group_id)

    async def _ensure_active_session(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
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

    async def _resolve_or_create_character(self, *, raw_name: str, slug: str) -> Character:
        existing = await self._character_store.get_by_id(slug)
        if existing is not None:
            return existing

        by_name = await self._character_store.find_by_name(raw_name)
        if by_name is not None:
            return by_name

        return await self._character_store.create_minimal(character_id=slug, name=raw_name)

    @staticmethod
    def _slugify(value: str) -> str:
        lowered = value.lower().strip()
        replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
        return replaced.strip("-")
