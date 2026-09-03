"""Import/export orchestration for scenarios and sessions (see ADR-024).

Backs both the once-per-boot curated-scenario seed and the admin panel's import/export
endpoints. Depends only on core ports, so it stays framework-free.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.lorebook_store import LorebookStore
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.infrastructure.scenario_serialization import (
    lore_entry_from_payload,
    lore_entry_to_payload,
    scenario_definition_from_payload,
    scenario_definition_to_payload,
    scenario_session_from_payload,
    scenario_session_to_payload,
)
from rp_engine.infrastructure.scenario_transfer import (
    read_scenario_directory,
    read_scenario_lorebook_directory,
)


def _message_to_payload(message: ConversationMessage) -> dict[str, Any]:
    return {"role": message.role.value, "content": message.content, "metadata": message.metadata}


def _message_from_payload(payload: dict[str, Any]) -> ConversationMessage:
    return ConversationMessage(
        role=ConversationRole(payload["role"]),
        content=payload["content"],
        metadata=payload.get("metadata", {}),
    )


@dataclass(frozen=True, slots=True)
class ImportReport:
    imported: int
    skipped: int


class ScenarioTransferService:
    def __init__(
        self,
        *,
        scenario_definition_store: ScenarioDefinitionStore,
        scenario_session_store: ScenarioSessionStore,
        conversation_store: ConversationStore,
        lorebook_store: LorebookStore,
    ) -> None:
        self._scenario_definition_store = scenario_definition_store
        self._scenario_session_store = scenario_session_store
        self._conversation_store = conversation_store
        self._lorebook_store = lorebook_store

    async def import_directory(self, path: Path | str) -> ImportReport:
        directory = Path(path)
        total_files = len(list(directory.glob("*.json"))) if directory.exists() else 0
        scenarios = read_scenario_directory(directory)
        for scenario in scenarios:
            await self._scenario_definition_store.save(scenario)
        # A scenario's optional `lorebook` array ships beside its definition and is
        # upserted the same way (ADR-026): a curated file is a seed, further edits
        # happen in the admin panel.
        for entry in read_scenario_lorebook_directory(directory):
            await self._lorebook_store.save(entry)
        return ImportReport(imported=len(scenarios), skipped=total_files - len(scenarios))

    async def import_scenario_payload(self, payload: dict[str, Any]) -> ScenarioDefinition | None:
        scenario = scenario_definition_from_payload(payload)
        if scenario is None:
            return None
        await self._scenario_definition_store.save(scenario)
        for raw_entry in payload.get("lorebook", []):
            if not isinstance(raw_entry, dict):
                continue
            entry = lore_entry_from_payload(raw_entry, scenario_definition_id=scenario.id)
            if entry is not None:
                await self._lorebook_store.save(entry)
        return scenario

    async def export_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        scenario = await self._scenario_definition_store.get_by_id(scenario_id)
        if scenario is None:
            return None
        payload = scenario_definition_to_payload(scenario)
        entries = await self._lorebook_store.list_for_scenario(scenario_id)
        payload["lorebook"] = [lore_entry_to_payload(entry) for entry in entries]
        return payload

    async def export_session(self, session_id: UUID) -> dict[str, Any] | None:
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            return None
        memory_key = ConversationIdentity.for_session(str(session_id)).to_memory_key()
        messages = await self._conversation_store.load_messages(memory_key)
        return {
            "session": scenario_session_to_payload(session),
            "transcript": [_message_to_payload(message) for message in messages],
        }

    async def import_session(self, payload: dict[str, Any]) -> ScenarioSession | None:
        session = scenario_session_from_payload(payload["session"])
        if session is None:
            return None
        saved = await self._scenario_session_store.save(session)
        memory_key = ConversationIdentity.for_session(str(saved.id)).to_memory_key()
        await self._conversation_store.clear(memory_key)
        for message_payload in payload.get("transcript", []):
            await self._conversation_store.save_message(
                memory_key, _message_from_payload(message_payload)
            )
        return saved
