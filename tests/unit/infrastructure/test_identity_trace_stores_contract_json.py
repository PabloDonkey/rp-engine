from pathlib import Path

import pytest

from rp_engine.infrastructure.storage.json_generation_trace_store import JsonGenerationTraceStore
from rp_engine.infrastructure.storage.json_group_identity_store import JsonGroupIdentityStore
from rp_engine.infrastructure.storage.json_user_identity_store import JsonUserIdentityStore
from tests.unit.infrastructure.contracts.generation_trace_store_contract import (
    assert_generation_trace_store_contract,
)
from tests.unit.infrastructure.contracts.group_identity_store_contract import (
    assert_group_identity_store_contract,
)
from tests.unit.infrastructure.contracts.user_identity_store_contract import (
    assert_user_identity_store_contract,
)


@pytest.mark.asyncio
async def test_json_user_identity_store_contract(tmp_path: Path) -> None:
    store = JsonUserIdentityStore(base_path=tmp_path)
    await assert_user_identity_store_contract(store)


@pytest.mark.asyncio
async def test_json_group_identity_store_contract(tmp_path: Path) -> None:
    store = JsonGroupIdentityStore(base_path=tmp_path)
    await assert_group_identity_store_contract(store)


@pytest.mark.asyncio
async def test_json_generation_trace_store_contract(tmp_path: Path) -> None:
    store = JsonGenerationTraceStore(base_path=tmp_path)
    await assert_generation_trace_store_contract(store)
