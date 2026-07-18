import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.character_card import CharacterCard
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.ports.character_store import CharacterStore

DEFAULT_OWNER_ID = UUID("00000000-0000-0000-0000-000000000000")


class JsonCharacterStore(CharacterStore):
    def __init__(self, base_path: Path | str = "data") -> None:
        self._characters_path = Path(base_path) / "characters"
        self._lock = asyncio.Lock()

    async def get_by_id(self, character_id: str) -> Character | None:
        card_path = self._characters_path / character_id / "card.json"
        if not card_path.exists():
            return None

        payload = await asyncio.to_thread(self._read_payload, card_path)
        return self._to_character(character_id=character_id, payload=payload)

    async def find_by_name(self, name: str) -> Character | None:
        target = name.strip().lower()
        if not self._characters_path.exists():
            return None

        for directory in self._characters_path.iterdir():
            if not directory.is_dir():
                continue
            card_path = directory / "card.json"
            if not card_path.exists():
                continue
            payload = await asyncio.to_thread(self._read_payload, card_path)
            character = self._to_character(character_id=directory.name, payload=payload)
            if character is not None and character.name.strip().lower() == target:
                return character
        return None

    async def find_owned_by_name(self, *, owner_id: UUID, name: str) -> Character | None:
        target = name.strip().lower()
        if not self._characters_path.exists():
            return None

        for directory in self._characters_path.iterdir():
            if not directory.is_dir():
                continue
            card_path = directory / "card.json"
            if not card_path.exists():
                continue
            payload = await asyncio.to_thread(self._read_payload, card_path)
            character = self._to_character(character_id=directory.name, payload=payload)
            if character is None:
                continue
            if character.owner_id == owner_id and character.name.strip().lower() == target:
                return character

        return None

    async def create_minimal(
        self,
        *,
        character_id: str,
        owner_id: UUID,
        name: str,
        visibility: CharacterVisibility = CharacterVisibility.PRIVATE,
    ) -> Character:
        async with self._lock:
            existing = await self.get_by_id(character_id)
            if existing is not None:
                return existing

            character_dir = self._characters_path / character_id
            character_dir.mkdir(parents=True, exist_ok=True)

            card = CharacterCard(
                name=name,
                description=f"Character profile for {name}.",
                personality="Open-ended roleplay persona.",
            )
            payload: dict[str, object] = {
                "id": character_id,
                "owner_id": str(owner_id),
                "visibility": visibility.value,
                "name": card.name,
                "description": card.description,
                "personality": card.personality,
                "speaking_style": card.speaking_style,
                "background": card.background,
                "metadata": card.metadata,
            }
            await asyncio.to_thread(self._write_payload, character_dir / "card.json", payload)
            return Character(
                id=character_id,
                owner_id=owner_id,
                visibility=visibility,
                name=card.name,
                description=card.description,
                personality=card.personality,
                greeting="",
                metadata={},
            )

    async def save(self, character: Character) -> Character:
        async with self._lock:
            character_dir = self._characters_path / character.id
            character_dir.mkdir(parents=True, exist_ok=True)
            payload: dict[str, object] = {
                "id": character.id,
                "owner_id": str(character.owner_id),
                "visibility": character.visibility.value,
                "name": character.name,
                "description": character.description,
                "personality": character.personality,
                "greeting": character.greeting,
                "metadata": dict(character.metadata),
            }
            await asyncio.to_thread(self._write_payload, character_dir / "card.json", payload)
        return character

    @staticmethod
    def _to_character(*, character_id: str, payload: dict[str, Any]) -> Character | None:
        owner_id = payload.get("owner_id")
        visibility = payload.get("visibility", CharacterVisibility.PRIVATE.value)
        name = payload.get("name")
        description = payload.get("description")
        personality = payload.get("personality")
        greeting = payload.get("greeting", "")
        metadata = payload.get("metadata", {})
        if not isinstance(name, str) or not isinstance(description, str) or not isinstance(
            personality,
            str,
        ):
            return None
        if not isinstance(greeting, str):
            greeting = ""
        if not isinstance(metadata, dict):
            metadata = {}
        normalized_metadata = {
            key: value
            for key, value in metadata.items()
            if isinstance(key, str) and isinstance(value, str)
        }

        parsed_owner_id = DEFAULT_OWNER_ID
        if isinstance(owner_id, str):
            try:
                parsed_owner_id = UUID(owner_id)
            except ValueError:
                parsed_owner_id = DEFAULT_OWNER_ID

        parsed_visibility = CharacterVisibility.PRIVATE
        if isinstance(visibility, str):
            try:
                parsed_visibility = CharacterVisibility(visibility)
            except ValueError:
                parsed_visibility = CharacterVisibility.PRIVATE

        return Character(
            id=character_id,
            owner_id=parsed_owner_id,
            visibility=parsed_visibility,
            name=name,
            description=description,
            personality=personality,
            greeting=greeting,
            metadata=normalized_metadata,
        )

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            return loaded
        return {}

    @staticmethod
    def _write_payload(path: Path, payload: dict[str, object]) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
