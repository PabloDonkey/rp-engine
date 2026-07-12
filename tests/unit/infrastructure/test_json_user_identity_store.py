from pathlib import Path

import pytest

from rp_engine.core.services.identity_resolver import IdentityResolver
from rp_engine.infrastructure.storage.json_user_identity_store import JsonUserIdentityStore


@pytest.mark.asyncio
async def test_json_user_identity_store_returns_same_user_after_reload(tmp_path: Path) -> None:
    store_one = JsonUserIdentityStore(base_path=tmp_path)
    resolver_one = IdentityResolver(store=store_one)

    first = await resolver_one.resolve_identity(
        provider="telegram",
        external_id="123456",
        display_name="Pablo",
        metadata={"username": "pablodonkey"},
    )

    store_two = JsonUserIdentityStore(base_path=tmp_path)
    resolver_two = IdentityResolver(store=store_two)
    second = await resolver_two.resolve_identity(
        provider="telegram",
        external_id="123456",
        display_name="Different Name",
        metadata={"username": "updated"},
    )

    assert second.id == first.id
    assert second.display_name == "Pablo"


@pytest.mark.asyncio
async def test_json_user_identity_store_creates_unique_users_for_different_identities(
    tmp_path: Path,
) -> None:
    store = JsonUserIdentityStore(base_path=tmp_path)
    resolver = IdentityResolver(store=store)

    first = await resolver.resolve_identity(
        provider="telegram",
        external_id="100",
        display_name="User One",
    )
    second = await resolver.resolve_identity(
        provider="telegram",
        external_id="200",
        display_name="User Two",
    )

    assert first.id != second.id
