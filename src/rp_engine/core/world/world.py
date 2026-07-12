from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class World:
    id: str
    name: str
    description: str
    rules: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
