from dataclasses import dataclass
from uuid import UUID, uuid4

from rp_engine.core.group.identity import GroupIdentity


@dataclass(frozen=True, slots=True)
class Group:
    id: UUID
    display_name: str
    identities: tuple[GroupIdentity, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        display_name: str,
        identities: tuple[GroupIdentity, ...] = (),
    ) -> "Group":
        return cls(id=uuid4(), display_name=display_name, identities=identities)
