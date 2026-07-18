from typing import Protocol
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility


class CharacterStore(Protocol):
    async def get_by_id(self, character_id: str) -> Character | None: ...

    async def find_by_name(self, name: str) -> Character | None: ...

    async def find_owned_by_name(self, *, owner_id: UUID, name: str) -> Character | None: ...

    async def create_minimal(
        self,
        *,
        character_id: str,
        owner_id: UUID,
        name: str,
        visibility: CharacterVisibility = CharacterVisibility.PRIVATE,
    ) -> Character: ...

    async def save(self, character: Character) -> Character: ...
