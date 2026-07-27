from pathlib import Path
from uuid import UUID, uuid4

import pytest

from rp_engine.adapters.telegram.pending_persona_store import TelegramPendingPersonaStore

SESSION_ID = UUID("00000000-0000-0000-0000-000000000099")


@pytest.mark.asyncio
async def test_get_missing_returns_none(tmp_path: Path) -> None:
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    assert await store.get(owner_kind="user", owner_id="42") is None


@pytest.mark.asyncio
async def test_set_then_get_round_trip(tmp_path: Path) -> None:
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    await store.set(owner_kind="user", owner_id="42", session_id=SESSION_ID)
    assert await store.get(owner_kind="user", owner_id="42") == SESSION_ID


@pytest.mark.asyncio
async def test_set_overwrites_an_abandoned_prompt(tmp_path: Path) -> None:
    # A second /play or /clear simply re-points the pending state at the newer session.
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    newer = uuid4()
    await store.set(owner_kind="user", owner_id="42", session_id=SESSION_ID)
    await store.set(owner_kind="user", owner_id="42", session_id=newer)
    assert await store.get(owner_kind="user", owner_id="42") == newer


@pytest.mark.asyncio
async def test_clear_removes_entry(tmp_path: Path) -> None:
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    await store.set(owner_kind="user", owner_id="42", session_id=SESSION_ID)
    await store.clear(owner_kind="user", owner_id="42")
    assert await store.get(owner_kind="user", owner_id="42") is None


@pytest.mark.asyncio
async def test_is_keyed_by_owner_kind_and_id(tmp_path: Path) -> None:
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    group_session = uuid4()
    await store.set(owner_kind="user", owner_id="42", session_id=SESSION_ID)
    await store.set(owner_kind="group", owner_id="42", session_id=group_session)
    assert await store.get(owner_kind="user", owner_id="42") == SESSION_ID
    assert await store.get(owner_kind="group", owner_id="42") == group_session


@pytest.mark.asyncio
async def test_clear_missing_is_noop(tmp_path: Path) -> None:
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    await store.clear(owner_kind="user", owner_id="nope")
    assert await store.get(owner_kind="user", owner_id="nope") is None


@pytest.mark.asyncio
async def test_a_corrupt_file_reads_as_no_pending_prompt(tmp_path: Path) -> None:
    store = TelegramPendingPersonaStore(base_path=tmp_path)
    file = tmp_path / "telegram" / "pending_personas" / "user_42.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("not json", encoding="utf-8")

    assert await store.get(owner_kind="user", owner_id="42") is None
