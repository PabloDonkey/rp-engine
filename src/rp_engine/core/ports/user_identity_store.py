from typing import Protocol

from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User


class UserIdentityStore(Protocol):
    async def get_user_by_identity(self, *, provider: str, external_id: str) -> User | None: ...

    async def create_user_with_identity(
        self,
        *,
        display_name: str,
        identity: UserIdentity,
    ) -> User: ...
