"""Scenario transfer: JSON files <-> `ScenarioDefinitionStore`.

Recycled from the old JSON-file `ScenarioCatalog` runtime loader (see ADR-024 in
`docs/adr/`): the directory-walk and per-file validation below used to be the
live source `/play` read from directly. Now Postgres is the live source, and this module
is only used to *import* curated scenarios into it — once at startup, and via the admin
panel's import/export endpoints (see `application/services/scenario_transfer_service.py`).
"""

import json
import logging
from pathlib import Path
from uuid import UUID

from rp_engine.core.scenario.lore_entry import LoreEntry
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.infrastructure.scenario_serialization import (
    lore_entry_from_payload,
    scenario_definition_from_payload,
)

logger = logging.getLogger(__name__)

# Curated scenarios are owned by the engine itself rather than any end user.
SYSTEM_OWNER_ID = UUID("00000000-0000-0000-0000-000000000000")


def read_scenario_directory(path: Path | str) -> list[ScenarioDefinition]:
    """Read + validate every `*.json` scenario file in a directory.

    Invalid files are logged and skipped rather than raised, matching the historical
    catalog-loader behavior this replaces.
    """
    directory = Path(path)
    if not directory.exists():
        logger.warning("Scenario import directory not found", extra={"path": str(directory)})
        return []

    scenarios: list[ScenarioDefinition] = []
    for file in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to read scenario file", extra={"file": str(file)})
            continue
        if not isinstance(payload, dict):
            logger.warning("Scenario file is not an object", extra={"file": str(file)})
            continue
        scenario = scenario_definition_from_payload(payload)
        if scenario is None:
            logger.warning("Scenario file failed validation", extra={"file": str(file)})
            continue
        scenarios.append(scenario)

    return scenarios


def read_scenario_lorebook_directory(path: Path | str) -> list[LoreEntry]:
    """Read every scenario file's optional `lorebook` array (ADR-026, S024).

    A scenario file's lore ships beside its scenario definition, the same seed-not-source
    relationship the catalog already has: this is how Jane's pilot entries reach Postgres
    on boot, and further edits then happen in the admin panel like any other lorebook
    entry. Kept as a second pass over the directory, rather than folded into
    `read_scenario_directory`, so that function's return type and existing callers are
    untouched.
    """
    directory = Path(path)
    if not directory.exists():
        return []

    entries: list[LoreEntry] = []
    for file in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        scenario_id = payload.get("id")
        if not isinstance(scenario_id, str):
            continue
        raw_entries = payload.get("lorebook", [])
        if not isinstance(raw_entries, list):
            logger.warning("Scenario lorebook is not a list", extra={"file": str(file)})
            continue
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            entry = lore_entry_from_payload(raw_entry, scenario_definition_id=scenario_id)
            if entry is None:
                logger.warning("Lorebook entry failed validation", extra={"file": str(file)})
                continue
            entries.append(entry)

    return entries
