"""Developer-curated scenario library loaded from JSON files.

Scenarios are authored as JSON documents (the same payload shape the scenario stores
persist) and dropped into a catalog directory. The catalog is read-only at runtime: it
provides the list of playable adventures for `/scenarios` and the blueprint that `/play`
turns into a per-player `ScenarioSession`.
"""

import json
import logging
from pathlib import Path
from uuid import UUID

from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.infrastructure.scenario_serialization import scenario_definition_from_payload

logger = logging.getLogger(__name__)

# Curated scenarios are owned by the engine itself rather than any end user.
SYSTEM_OWNER_ID = UUID("00000000-0000-0000-0000-000000000000")


class ScenarioCatalog:
    def __init__(self, scenarios: list[ScenarioDefinition]) -> None:
        self._by_id = {scenario.id: scenario for scenario in scenarios}

    @classmethod
    def from_directory(cls, path: Path | str) -> "ScenarioCatalog":
        directory = Path(path)
        if not directory.exists():
            logger.warning("Scenario catalog directory not found", extra={"path": str(directory)})
            return cls([])

        scenarios: list[ScenarioDefinition] = []
        for file in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.exception("Failed to read catalog scenario", extra={"file": str(file)})
                continue
            if not isinstance(payload, dict):
                logger.warning("Catalog scenario is not an object", extra={"file": str(file)})
                continue
            scenario = scenario_definition_from_payload(payload)
            if scenario is None:
                logger.warning("Catalog scenario failed validation", extra={"file": str(file)})
                continue
            scenarios.append(scenario)

        logger.info("Scenario catalog loaded", extra={"count": len(scenarios)})
        return cls(scenarios)

    def list(self) -> list[ScenarioDefinition]:
        return sorted(self._by_id.values(), key=lambda scenario: scenario.name.lower())

    def get(self, scenario_id: str) -> ScenarioDefinition | None:
        return self._by_id.get(scenario_id)

    def is_empty(self) -> bool:
        return not self._by_id
