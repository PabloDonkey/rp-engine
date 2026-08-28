from datetime import UTC, datetime
from uuid import UUID

import pytest

from rp_engine.core.scenario.scenario_session import ScenarioSession


@pytest.fixture
def sample_user_id() -> UUID:
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_group_id() -> UUID:
    return UUID("87654321-4321-8765-4321-876543218765")


def test_scenario_session_creation(sample_user_id: UUID) -> None:
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
    )

    assert session.scenario_definition_id == "scenario_1"
    assert session.owner_kind == "user"
    assert session.owner_id == sample_user_id
    assert session.active_participants == {}
    assert session.world_state == {}
    assert session.story_progress == {}
    assert session.metadata == {}


def test_scenario_session_with_participants(sample_user_id: UUID) -> None:
    participants = {"protagonist": "char_1", "antagonist": "char_2"}
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
        active_participants=participants,
    )

    assert session.active_participants == participants


def test_scenario_session_with_world_state(sample_user_id: UUID) -> None:
    world_state = {"location": "forest", "time": "night", "weather": "rainy"}
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
        world_state=world_state,
    )

    assert session.world_state == world_state


def test_scenario_session_with_story_progress(sample_user_id: UUID) -> None:
    story_progress = {
        "act": 1,
        "current_quest": "rescue_princess",
        "completed_quests": ["find_map"],
    }
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
        story_progress=story_progress,
    )

    assert session.story_progress == story_progress


def test_scenario_session_with_metadata(sample_user_id: UUID) -> None:
    metadata = {"difficulty": "hard", "mode": "hardcore"}
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
        metadata=metadata,
    )

    assert session.metadata == metadata


def test_scenario_session_has_timestamp(sample_user_id: UUID) -> None:
    before = datetime.now(UTC)
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
    )
    after = datetime.now(UTC)

    assert before <= session.created_at <= after


def test_scenario_session_immutability(sample_user_id: UUID) -> None:
    session = ScenarioSession(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=sample_user_id,
    )

    with pytest.raises(AttributeError):
        session.scenario_definition_id = "scenario_2"  # type: ignore


def test_scenario_session_create_for_user(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1",
        user_id=sample_user_id,
    )

    assert session.scenario_definition_id == "scenario_1"
    assert session.owner_kind == "user"
    assert session.owner_id == sample_user_id
    assert session.active_participants == {}
    assert session.world_state == {}
    assert session.story_progress == {}
    assert session.metadata == {}


def test_scenario_session_create_for_user_with_full_context(sample_user_id: UUID) -> None:
    participants = {"protagonist": "char_1"}
    world_state = {"location": "castle"}
    story_progress = {"chapter": 1}
    metadata = {"difficulty": "medium"}

    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1",
        user_id=sample_user_id,
        active_participants=participants,
        world_state=world_state,
        story_progress=story_progress,
        metadata=metadata,
    )

    assert session.owner_kind == "user"
    assert session.owner_id == sample_user_id
    assert session.active_participants == participants
    assert session.world_state == world_state
    assert session.story_progress == story_progress
    assert session.metadata == metadata


def test_scenario_session_create_for_group(sample_group_id: UUID) -> None:
    session = ScenarioSession.create_for_group(
        scenario_definition_id="scenario_1",
        group_id=sample_group_id,
    )

    assert session.scenario_definition_id == "scenario_1"
    assert session.owner_kind == "group"
    assert session.owner_id == sample_group_id
    assert session.active_participants == {}
    assert session.world_state == {}
    assert session.story_progress == {}
    assert session.metadata == {}


def test_scenario_session_create_for_group_with_full_context(sample_group_id: UUID) -> None:
    participants = {"protagonist": "char_1", "narrator": "char_2"}
    world_state = {"location": "tavern"}
    story_progress = {"scene": 2}
    metadata = {"game_master": "user_1"}

    session = ScenarioSession.create_for_group(
        scenario_definition_id="scenario_1",
        group_id=sample_group_id,
        active_participants=participants,
        world_state=world_state,
        story_progress=story_progress,
        metadata=metadata,
    )

    assert session.owner_kind == "group"
    assert session.owner_id == sample_group_id
    assert session.active_participants == participants
    assert session.world_state == world_state
    assert session.story_progress == story_progress
    assert session.metadata == metadata


def test_scenario_session_has_unique_ids() -> None:
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    session1 = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1",
        user_id=user_id,
    )
    session2 = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1",
        user_id=user_id,
    )

    assert session1.id != session2.id


def test_with_persona_sets_name_and_description(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    )

    updated = session.with_persona(name="  Sera Vane  ", description="  A wary courier.  ")

    assert updated.user_persona_name == "Sera Vane"
    assert updated.user_persona_description == "A wary courier."
    assert updated.has_persona is True
    # The original is untouched — the session is immutable like the rest of the domain.
    assert session.has_persona is False


def test_with_persona_stores_a_missing_description_as_none(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    ).with_persona(name="Kes")

    assert session.user_persona_description is None


def test_with_persona_rejects_a_second_persona(sample_user_id: UUID) -> None:
    """Immutable once set: the name is substituted into every prompt and into the
    transcript already written, so changing it would rewrite history."""
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    ).with_persona(name="Sera Vane")

    with pytest.raises(ValueError, match="immutable"):
        session.with_persona(name="Someone Else")


def test_with_persona_rejects_a_blank_name(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    )

    with pytest.raises(ValueError):
        session.with_persona(name="   ")


def test_resolve_user_name_prefers_the_persona_over_the_fallback(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    )

    assert session.resolve_user_name("Pablo") == "Pablo"
    assert session.with_persona(name="Sera Vane").resolve_user_name("Pablo") == "Sera Vane"


def test_mark_deleted_stamps_a_live_session(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    )
    assert session.is_deleted is False

    superseded = session.mark_deleted(at=datetime(2026, 7, 27, tzinfo=UTC))

    assert superseded.is_deleted is True
    assert superseded.deleted_at == datetime(2026, 7, 27, tzinfo=UTC)


def test_mark_deleted_keeps_the_original_timestamp(sample_user_id: UUID) -> None:
    # Idempotent, so re-superseding never falsifies *when* a session actually ended.
    first = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    ).mark_deleted(at=datetime(2026, 7, 27, tzinfo=UTC))

    assert first.mark_deleted(at=datetime(2026, 7, 28, tzinfo=UTC)) is first


def test_override_persona_replaces_an_existing_one(sample_user_id: UUID) -> None:
    """The operator escape hatch. Kept separate from `with_persona` so the set-once guard
    keeps protecting every path a player can reach."""
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    ).with_persona(name="Sera Vane", description="A wary courier.")

    corrected = session.override_persona(name="Sera Vayne", description="A wary courier.")

    assert corrected.user_persona_name == "Sera Vayne"
    assert corrected.user_persona_description == "A wary courier."


def test_override_persona_also_sets_a_first_one(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    ).override_persona(name="Kes")

    assert session.user_persona_name == "Kes"
    assert session.user_persona_description is None


def test_override_persona_still_rejects_a_blank_name(sample_user_id: UUID) -> None:
    session = ScenarioSession.create_for_user(
        scenario_definition_id="scenario_1", user_id=sample_user_id
    ).with_persona(name="Sera Vane")

    with pytest.raises(ValueError):
        session.override_persona(name="  ")
