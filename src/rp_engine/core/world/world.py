from dataclasses import dataclass, field

from rp_engine.core.metadata import Metadata


@dataclass(frozen=True, slots=True)
class World:
    id: str
    name: str
    description: str
    rules: tuple[str, ...] = ()
    metadata: Metadata = field(default_factory=dict)
