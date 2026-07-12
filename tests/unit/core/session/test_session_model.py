from uuid import UUID

from rp_engine.core.session.session import Session


def test_session_create_sets_relationship_fields() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000111")

    session = Session.create(user_id=user_id, character_id="belzebuth", world_id="fantasy")

    assert session.user_id == user_id
    assert session.character_id == "belzebuth"
    assert session.world_id == "fantasy"
