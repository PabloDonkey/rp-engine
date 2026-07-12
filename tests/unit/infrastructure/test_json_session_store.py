from pathlib import Path
from uuid import UUID

import pytest

from rp_engine.core.session.session import Session
from rp_engine.infrastructure.storage.json_session_store import JsonSessionStore


@pytest.mark.asyncio
async def test_json_session_store_saves_and_loads_session(tmp_path: Path) -> None:
    store = JsonSessionStore(base_path=tmp_path)
    user_id = UUID("00000000-0000-0000-0000-000000000010")
    session = Session.create_for_user(user_id=user_id, character_id="belzebuth", world_id="default")

    await store.save(session)
    loaded = await store.get_by_id(session.id)

    assert loaded is not None
    assert loaded.id == session.id
    assert loaded.owner_kind == "user"
    assert loaded.owner_id == user_id


@pytest.mark.asyncio
async def test_json_session_store_tracks_active_session_per_user(tmp_path: Path) -> None:
    store = JsonSessionStore(base_path=tmp_path)
    user_id = UUID("00000000-0000-0000-0000-000000000011")
    session = Session.create_for_user(user_id=user_id, character_id="alice", world_id="default")

    await store.save(session)
    await store.set_active_for_owner(owner_kind="user", owner_id=user_id, session_id=session.id)
    active = await store.get_active_for_owner(owner_kind="user", owner_id=user_id)

    assert active is not None
    assert active.id == session.id
