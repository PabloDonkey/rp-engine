from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User


def test_user_create_generates_unique_internal_ids() -> None:
    user_one = User.create(display_name="Alice")
    user_two = User.create(display_name="Bob")

    assert user_one.id != user_two.id


def test_user_model_is_provider_agnostic() -> None:
    identity = UserIdentity(
        provider="custom-provider",
        external_id="abc-123",
        metadata={"k": "v"},
    )
    user = User.create(display_name="Alice", identities=(identity,))

    assert user.display_name == "Alice"
    assert user.identities[0].provider == "custom-provider"
