from pathlib import Path

import pytest

from rp_engine.infrastructure.storage.json_world_store import JsonWorldStore


@pytest.mark.asyncio
async def test_json_world_store_create_default_and_load(tmp_path: Path) -> None:
    store = JsonWorldStore(base_path=tmp_path)

    created = await store.create_default(world_id="default")
    loaded = await store.get_by_id("default")

    assert created.id == "default"
    assert loaded is not None
    assert loaded.id == "default"
