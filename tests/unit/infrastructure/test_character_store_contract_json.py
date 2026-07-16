from pathlib import Path

import pytest

from rp_engine.infrastructure.storage.json_character_store import JsonCharacterStore
from tests.unit.infrastructure.contracts.character_store_contract import (
    assert_character_store_contract,
)


@pytest.mark.asyncio
async def test_json_character_store_contract(tmp_path: Path) -> None:
    store = JsonCharacterStore(base_path=tmp_path)
    await assert_character_store_contract(store)
