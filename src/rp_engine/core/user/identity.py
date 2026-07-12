from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserIdentity:
    provider: str
    external_id: str
    metadata: dict[str, str]
