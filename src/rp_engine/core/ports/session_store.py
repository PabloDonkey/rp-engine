from typing import Protocol
from uuid import UUID

from rp_engine.core.session.session import Session, SessionOwnerKind


class SessionStore(Protocol):
    async def get_by_id(self, session_id: UUID) -> Session | None: ...

    async def find_by_relationship(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        character_id: str,
        world_id: str,
    ) -> Session | None: ...

    async def save(self, session: Session) -> Session: ...

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None: ...

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> Session | None: ...
