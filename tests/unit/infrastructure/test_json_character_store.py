from pathlib import Path
from uuid import UUID

import pytest

from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.infrastructure.storage.json_character_store import JsonCharacterStore


@pytest.mark.asyncio
async def test_json_character_store_creates_card_file(tmp_path: Path) -> None:
    store = JsonCharacterStore(base_path=tmp_path)
    owner_id = UUID("00000000-0000-0000-0000-000000000123")

    created = await store.create_minimal(
        character_id="belzebuth",
        owner_id=owner_id,
        name="Belzebuth",
    )

    assert created.id == "belzebuth"
    assert created.owner_id == owner_id
    assert created.visibility == CharacterVisibility.PRIVATE
    assert (tmp_path / "characters" / "belzebuth" / "card.json").exists()


@pytest.mark.asyncio
async def test_json_character_store_finds_character_by_name(tmp_path: Path) -> None:
    store = JsonCharacterStore(base_path=tmp_path)
    await store.create_minimal(
        character_id="belzebuth",
        owner_id=UUID("00000000-0000-0000-0000-000000000123"),
        name="Belzebuth",
    )

    found = await store.find_by_name("belzebuth")

    assert found is not None
    assert found.id == "belzebuth"
