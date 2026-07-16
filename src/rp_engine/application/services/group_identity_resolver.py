from rp_engine.core.group.group import Group
from rp_engine.core.group.identity import GroupIdentity
from rp_engine.core.ports.group_identity_store import GroupIdentityStore


class GroupIdentityResolver:
    def __init__(self, store: GroupIdentityStore) -> None:
        self._store = store

    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group:
        existing = await self._store.get_group_by_identity(
            provider=provider,
            external_id=external_id,
        )
        if existing is not None:
            return existing

        identity = GroupIdentity(
            provider=provider,
            external_id=external_id,
            metadata=metadata or {},
        )
        return await self._store.create_group_with_identity(
            display_name=display_name,
            identity=identity,
        )
