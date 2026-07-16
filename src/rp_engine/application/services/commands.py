from dataclasses import dataclass

from rp_engine.core.character.visibility import CharacterVisibility


@dataclass(frozen=True, slots=True)
class SelectCharacterCommand:
    character_name: str
    visibility: CharacterVisibility = CharacterVisibility.PRIVATE
