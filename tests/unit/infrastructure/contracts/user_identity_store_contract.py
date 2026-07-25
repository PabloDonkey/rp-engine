from rp_engine.core.ports.user_identity_store import UserIdentityStore
from rp_engine.core.user.identity import UserIdentity


async def assert_user_identity_store_contract(store: UserIdentityStore) -> None:
    identity = UserIdentity(
        provider="telegram", external_id="123456", metadata={"username": "pablodonkey"}
    )

    assert await store.get_user_by_identity(provider="telegram", external_id="123456") is None

    user = await store.create_user_with_identity(display_name="Pablo", identity=identity)
    assert user.display_name == "Pablo"
    assert user.identities == (identity,)

    by_id = await store.get_by_id(user.id)
    assert by_id == user

    by_identity = await store.get_user_by_identity(provider="telegram", external_id="123456")
    assert by_identity == user

    # Re-creating with the same identity is idempotent and returns the original user.
    again = await store.create_user_with_identity(
        display_name="Different Name",
        identity=UserIdentity(provider="telegram", external_id="123456", metadata={}),
    )
    assert again.id == user.id
    assert again.display_name == "Pablo"

    # A distinct identity creates a distinct user.
    other = await store.create_user_with_identity(
        display_name="Other",
        identity=UserIdentity(provider="telegram", external_id="999", metadata={}),
    )
    assert other.id != user.id

    assert await store.get_by_id(other.id) is not None

    all_users = await store.list_users()
    assert {listed.id for listed in all_users} == {user.id, other.id}
