from typing import Protocol
from uuid import UUID

from rp_engine.core.group.group import Group
from rp_engine.core.group.identity import GroupIdentity


class GroupIdentityStore(Protocol):
    async def get_by_id(self, group_id: UUID) -> Group | None: ...

    async def get_group_by_identity(self, *, provider: str, external_id: str) -> Group | None: ...

    async def create_group_with_identity(
        self,
        *,
        display_name: str,
        identity: GroupIdentity,
    ) -> Group: ...
