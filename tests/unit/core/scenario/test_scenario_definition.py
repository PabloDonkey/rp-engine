from uuid import UUID

import pytest

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
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
        owner_id=UUID("12345678-1234-5678-1234-567812345678"),
        visibility=CharacterVisibility.PRIVATE,
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
    assert scenario.metadata == {}
