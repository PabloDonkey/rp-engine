from typing import Protocol

from rp_engine.core.user.user import User


class IdentityResolverPort(Protocol):
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User: ...
