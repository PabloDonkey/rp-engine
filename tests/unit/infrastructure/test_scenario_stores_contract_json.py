from pathlib import Path

import pytest

from rp_engine.infrastructure.storage.json_scenario_definition_store import (
    JsonScenarioDefinitionStore,
)
from rp_engine.infrastructure.storage.json_scenario_session_store import (
    JsonScenarioSessionStore,
)
from tests.unit.infrastructure.contracts.scenario_definition_store_contract import (
    assert_minimal_scenario_round_trip,
    assert_scenario_definition_store_contract,
)
from tests.unit.infrastructure.contracts.scenario_session_store_contract import (
    assert_scenario_session_store_contract,
)


@pytest.mark.asyncio
async def test_json_scenario_definition_store_contract(tmp_path: Path) -> None:
    store = JsonScenarioDefinitionStore(base_path=tmp_path)
    await assert_scenario_definition_store_contract(store)
    await assert_minimal_scenario_round_trip(store)


@pytest.mark.asyncio
async def test_json_scenario_session_store_contract(tmp_path: Path) -> None:
    store = JsonScenarioSessionStore(base_path=tmp_path)
    await assert_scenario_session_store_contract(store)
