from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GroupIdentity:
    provider: str
    external_id: str
    metadata: dict[str, str]
