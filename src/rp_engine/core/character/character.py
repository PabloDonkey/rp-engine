from dataclasses import dataclass, field
from uuid import UUID

from rp_engine.core.character.visibility import CharacterVisibility


@dataclass(frozen=True, slots=True)
class Character:
    id: str
    owner_id: UUID
    visibility: CharacterVisibility
    name: str
    description: str
    personality: str
    greeting: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
