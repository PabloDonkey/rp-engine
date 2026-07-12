from dataclasses import dataclass
from uuid import UUID, uuid4

from rp_engine.core.user.identity import UserIdentity


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    display_name: str
    identities: tuple[UserIdentity, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        display_name: str,
        identities: tuple[UserIdentity, ...] = (),
    ) -> "User":
        return cls(id=uuid4(), display_name=display_name, identities=identities)
