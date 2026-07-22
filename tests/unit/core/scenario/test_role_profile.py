import pytest

from rp_engine.core.scenario.role_profile import RoleProfile


def test_role_profile_minimal():
    profile = RoleProfile(id="protagonist", name="Protagonist")

    assert profile.id == "protagonist"
    assert profile.name == "Protagonist"
    assert profile.description == ""
    assert profile.objectives == ()
    assert profile.constraints == ()
    assert profile.metadata == {}


def test_role_profile_full():
    profile = RoleProfile(
        id="antagonist",
        name="The Rival",
        description="A cunning opponent",
        objectives=("thwart the hero", "seize the artifact"),
        constraints=("never break character", "avoid direct violence"),
        metadata={"alignment": "chaotic"},
    )

    assert profile.description == "A cunning opponent"
    assert profile.objectives == ("thwart the hero", "seize the artifact")
    assert profile.constraints == ("never break character", "avoid direct violence")
    assert profile.metadata == {"alignment": "chaotic"}


def test_role_profile_immutability():
    profile = RoleProfile(id="narrator", name="Narrator")

    with pytest.raises(AttributeError):
        profile.name = "Something Else"  # type: ignore
