import asyncio
from uuid import UUID

from rp_engine.application.services.identity_resolver import IdentityResolver
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User


class FakeIdentityStore:
    def __init__(self) -> None:
        self._existing: User | None = None
        self.created_count = 0

    async def get_user_by_identity(self, *, provider: str, external_id: str) -> User | None:
        del provider
        del external_id
        return self._existing

    async def get_by_id(self, user_id: UUID) -> User | None:
        del user_id
        return self._existing

    async def create_user_with_identity(
        self,
        *,
        display_name: str,
        identity: UserIdentity,
    ) -> User:
        self.created_count += 1
        user = User.create(display_name=display_name, identities=(identity,))
        self._existing = user
        return user


def test_identity_resolver_creates_when_identity_is_unknown() -> None:
    store = FakeIdentityStore()
    resolver = IdentityResolver(store=store)

    user = asyncio.run(
        resolver.resolve_identity(
            provider="telegram",
            external_id="123",
            display_name="Alice",
            metadata={"username": "alice"},
        )
    )

    assert user.display_name == "Alice"
    assert store.created_count == 1


def test_identity_resolver_returns_existing_user() -> None:
    store = FakeIdentityStore()
    existing = User.create(display_name="Existing")
    store._existing = existing
    resolver = IdentityResolver(store=store)

    user = asyncio.run(
        resolver.resolve_identity(
            provider="telegram",
            external_id="123",
            display_name="Ignored",
        )
    )

    assert user.id == existing.id
    assert store.created_count == 0
