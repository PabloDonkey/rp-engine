from rp_engine.core.ports.user_identity_store import UserIdentityStore
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User


class IdentityResolver:
    def __init__(self, store: UserIdentityStore) -> None:
        self._store = store

    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User:
        existing = await self._store.get_user_by_identity(
            provider=provider,
            external_id=external_id,
        )
        if existing is not None:
            return existing

        identity = UserIdentity(
            provider=provider,
            external_id=external_id,
            metadata=metadata or {},
        )
        return await self._store.create_user_with_identity(
            display_name=display_name,
            identity=identity,
        )
