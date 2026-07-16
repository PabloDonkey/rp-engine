from uuid import UUID

from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.ports.character_store import CharacterStore


async def assert_character_store_contract(store: CharacterStore) -> None:
    owner_id = UUID("00000000-0000-0000-0000-000000000123")

    created = await store.create_minimal(
        character_id="belzebuth",
        owner_id=owner_id,
        name="Belzebuth",
    )

    assert created.id == "belzebuth"
    assert created.owner_id == owner_id
    assert created.visibility == CharacterVisibility.PRIVATE

    loaded = await store.get_by_id("belzebuth")
    assert loaded is not None
    assert loaded.owner_id == owner_id
    assert loaded.visibility == CharacterVisibility.PRIVATE

    found = await store.find_by_name("belzebuth")
    assert found is not None
    assert found.id == "belzebuth"
    assert found.owner_id == owner_id

    duplicate = await store.create_minimal(
        character_id="belzebuth",
        owner_id=UUID("00000000-0000-0000-0000-000000000999"),
        name="Belzebuth",
    )
    assert duplicate.id == "belzebuth"
    assert duplicate.owner_id == owner_id

    custom_visibility = await store.create_minimal(
        character_id="behemoth",
        owner_id=owner_id,
        name="Behemoth",
        visibility=CharacterVisibility.PUBLIC,
    )
    assert custom_visibility.visibility == CharacterVisibility.PUBLIC

    loaded_custom = await store.get_by_id("behemoth")
    assert loaded_custom is not None
    assert loaded_custom.owner_id == owner_id
    assert loaded_custom.visibility == CharacterVisibility.PUBLIC
