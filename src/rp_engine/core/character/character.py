from dataclasses import dataclass, field

from rp_engine.core.metadata import Metadata


@dataclass(frozen=True, slots=True)
class Character:
    id: str
    name: str
    description: str
    personality: str
    greeting: str = ""
    metadata: Metadata = field(default_factory=dict)
