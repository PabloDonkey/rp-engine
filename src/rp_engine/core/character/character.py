from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Character:
    id: str
    name: str
    description: str
    personality: str
    greeting: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
