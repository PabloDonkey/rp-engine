from rp_engine.core.group.identity import GroupIdentity
from rp_engine.core.ports.group_identity_store import GroupIdentityStore


async def assert_group_identity_store_contract(store: GroupIdentityStore) -> None:
    identity = GroupIdentity(
        provider="telegram", external_id="-100123", metadata={"title": "Adventurers"}
    )

    assert await store.get_group_by_identity(provider="telegram", external_id="-100123") is None

    group = await store.create_group_with_identity(display_name="Adventurers", identity=identity)
    assert group.display_name == "Adventurers"
    assert group.identities == (identity,)

    by_id = await store.get_by_id(group.id)
    assert by_id == group

    by_identity = await store.get_group_by_identity(provider="telegram", external_id="-100123")
    assert by_identity == group

    # Re-creating with the same identity is idempotent and returns the original group.
    again = await store.create_group_with_identity(
        display_name="Different Name",
        identity=GroupIdentity(provider="telegram", external_id="-100123", metadata={}),
    )
    assert again.id == group.id
    assert again.display_name == "Adventurers"

    # A distinct identity creates a distinct group.
    other = await store.create_group_with_identity(
        display_name="Other",
        identity=GroupIdentity(provider="telegram", external_id="-999", metadata={}),
    )
    assert other.id != group.id

    assert await store.get_by_id(other.id) is not None
