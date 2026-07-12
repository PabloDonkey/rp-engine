from typing import Protocol

from rp_engine.core.character.character import Character


class CharacterStore(Protocol):
    async def get_by_id(self, character_id: str) -> Character | None: ...

    async def find_by_name(self, name: str) -> Character | None: ...

    async def create_minimal(self, *, character_id: str, name: str) -> Character: ...
