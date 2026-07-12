from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelectCharacterCommand:
    character_name: str
