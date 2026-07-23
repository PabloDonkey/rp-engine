from uuid import UUID

import pytest

from rp_engine.core.character.character import Character
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.visibility import ScenarioVisibility
from rp_engine.core.world.world import World


@pytest.fixture
def sample_world() -> World:
    return World(
        id="test_world",
        name="Test World",
        description="A world for testing",
        rules=["No violence", "Be respectful"],
        metadata={},
    )


@pytest.fixture
def sample_character() -> Character:
    return Character(
        id="test_char",
        name="Test Character",
        description="A test character",
        personality="Friendly and helpful",
        greeting="Hello, nice to meet you!",
        metadata={},
    )


def test_scenario_definition_creation():
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
    )

    assert scenario.id == "scenario_1"
    assert scenario.owner_id == owner_id
    assert scenario.name == "Test Scenario"
    assert scenario.description == "A test scenario"
    assert scenario.world is None
    assert scenario.characters == {}
    assert scenario.rules == []
    assert scenario.initial_context == ""
    assert scenario.metadata == {}


def test_scenario_definition_with_world(sample_world: World):
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
        world=sample_world,
    )

    assert scenario.world is sample_world


def test_scenario_definition_with_characters(sample_character: Character):
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    characters = {"protagonist": sample_character}
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
        characters=characters,
    )

    assert scenario.characters == characters
    assert scenario.characters["protagonist"] == sample_character


def test_scenario_definition_with_rules():
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    rules = ["Be respectful", "No violence", "Stay in character"]
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
        rules=rules,
    )

    assert scenario.rules == rules


def test_scenario_definition_with_initial_context():
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    context = "It is a dark and stormy night..."
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
        initial_context=context,
    )

    assert scenario.initial_context == context


def test_scenario_definition_with_metadata():
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    metadata = {"genre": "fantasy", "difficulty": "hard"}
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
        metadata=metadata,
    )

    assert scenario.metadata == metadata


def test_scenario_definition_immutability():
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
    )

    with pytest.raises(AttributeError):
        scenario.name = "Different Name"  # type: ignore


def test_scenario_definition_factory_method(sample_world: World, sample_character: Character):
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    characters = {"protagonist": sample_character}
    rules = ["Be respectful"]
    metadata = {"genre": "fantasy"}

    scenario = ScenarioDefinition.create(
        scenario_id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
        world=sample_world,
        characters=characters,
        rules=rules,
        initial_context="Opening context",
        metadata=metadata,
    )

    assert scenario.id == "scenario_1"
    assert scenario.owner_id == owner_id
    assert scenario.name == "Test Scenario"
    assert scenario.world == sample_world
    assert scenario.characters == characters
    assert scenario.rules == rules
    assert scenario.initial_context == "Opening context"
    assert scenario.metadata == metadata


def test_scenario_definition_factory_with_defaults():
    owner_id = UUID("12345678-1234-5678-1234-567812345678")
    scenario = ScenarioDefinition.create(
        scenario_id="scenario_1",
        owner_id=owner_id,
        name="Test Scenario",
        description="A test scenario",
    )

    assert scenario.world is None
    assert scenario.characters == {}
    assert scenario.rules == []
    assert scenario.initial_context == ""
    assert scenario.visibility is ScenarioVisibility.PUBLIC
    assert scenario.allowed_group_chat_ids == ()
    assert scenario.metadata == {}


def _scenario(**overrides: object) -> ScenarioDefinition:
    base: dict[str, object] = {
        "id": "s1",
        "owner_id": UUID("12345678-1234-5678-1234-567812345678"),
        "name": "S",
        "description": "d",
    }
    base.update(overrides)
    return ScenarioDefinition(**base)  # type: ignore[arg-type]


def test_public_scenario_is_listed_and_playable_for_everyone():
    scenario = _scenario(visibility=ScenarioVisibility.PUBLIC)

    assert scenario.is_listed_for(None) is True
    assert scenario.is_listed_for("g1") is True
    assert scenario.is_playable_by(None) is True


def test_unlisted_scenario_is_hidden_but_playable():
    scenario = _scenario(visibility=ScenarioVisibility.UNLISTED)

    assert scenario.is_listed_for(None) is False
    assert scenario.is_listed_for("g1") is False
    assert scenario.is_playable_by(None) is True


def test_restricted_scenario_only_for_allowed_group():
    scenario = _scenario(
        visibility=ScenarioVisibility.RESTRICTED,
        allowed_group_chat_ids=("g1",),
    )

    assert scenario.is_listed_for("g1") is True
    assert scenario.is_playable_by("g1") is True
    # Outsiders (other groups and direct chats) are excluded from both.
    assert scenario.is_listed_for("g2") is False
    assert scenario.is_playable_by("g2") is False
    assert scenario.is_listed_for(None) is False
    assert scenario.is_playable_by(None) is False
