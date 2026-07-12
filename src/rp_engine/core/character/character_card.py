from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CharacterCard:
    name: str
    description: str
    personality: str
    speaking_style: str = ""
    background: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
