from pathlib import Path

import pytest

from rp_engine.infrastructure.storage import JsonConversationStore
from tests.unit.infrastructure.contracts.conversation_store_contract import (
    assert_conversation_store_contract,
)


@pytest.mark.asyncio
async def test_json_conversation_store_contract(tmp_path: Path) -> None:
    store = JsonConversationStore(base_path=tmp_path)
    await assert_conversation_store_contract(store)
