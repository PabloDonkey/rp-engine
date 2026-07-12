from pathlib import Path

import pytest

from rp_engine.infrastructure.storage.json_character_store import JsonCharacterStore


@pytest.mark.asyncio
async def test_json_character_store_creates_card_and_state_files(tmp_path: Path) -> None:
    store = JsonCharacterStore(base_path=tmp_path)

    created = await store.create_minimal(character_id="belzebuth", name="Belzebuth")

    assert created.id == "belzebuth"
    assert (tmp_path / "characters" / "belzebuth" / "card.json").exists()
    assert (tmp_path / "characters" / "belzebuth" / "state.json").exists()


@pytest.mark.asyncio
async def test_json_character_store_finds_character_by_name(tmp_path: Path) -> None:
    store = JsonCharacterStore(base_path=tmp_path)
    await store.create_minimal(character_id="belzebuth", name="Belzebuth")

    found = await store.find_by_name("belzebuth")

    assert found is not None
    assert found.id == "belzebuth"
