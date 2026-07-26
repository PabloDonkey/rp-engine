from pathlib import Path
from uuid import UUID

import pytest

from rp_engine.application.services.scenario_transfer_service import ScenarioTransferService
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.infrastructure.scenario_serialization import scenario_definition_to_payload
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID

USER_ID = UUID("00000000-0000-0000-0000-000000000042")


class FakeScenarioDefinitionStore:
    def __init__(self) -> None:
        self.items: dict[str, ScenarioDefinition] = {}

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        return self.items.get(scenario_id)

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        return [s for s in self.items.values() if s.owner_id == owner_id]

    async def list_all(self) -> list[ScenarioDefinition]:
        return list(self.items.values())

    async def save(self, scenario: ScenarioDefinition) -> None:
        self.items[scenario.id] = scenario

    async def delete(self, scenario_id: str) -> None:
        self.items.pop(scenario_id, None)


class FakeScenarioSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[UUID, ScenarioSession] = {}

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        return self.sessions.get(session_id)

    async def find_by_owner(self, owner_kind: str, owner_id: UUID) -> list[ScenarioSession]:
        return [
            s
            for s in self.sessions.values()
            if s.owner_kind == owner_kind and s.owner_id == owner_id
        ]

    async def find_by_definition(
        self, *, owner_kind: str, owner_id: UUID, scenario_definition_id: str
    ) -> ScenarioSession | None:
        return None

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        self.sessions[session.id] = session
        return session

    async def delete(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)

    async def set_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID, session_id: UUID
    ) -> None:
        pass

    async def get_active_for_owner(
        self, *, owner_kind: str, owner_id: UUID
    ) -> ScenarioSession | None:
        return None


class FakeConversationStore:
    def __init__(self) -> None:
        self.messages: dict[str, list[ConversationMessage]] = {}

    async def save_message(self, memory_key: MemoryKey, message: ConversationMessage) -> None:
        self.messages.setdefault(memory_key.value, []).append(message)

    async def load_messages(self, memory_key: MemoryKey) -> list[ConversationMessage]:
        return list(self.messages.get(memory_key.value, []))

    async def clear(self, memory_key: MemoryKey) -> None:
        self.messages.pop(memory_key.value, None)


def _service() -> tuple[
    ScenarioTransferService, FakeScenarioDefinitionStore, FakeScenarioSessionStore,
    FakeConversationStore,
]:
    definition_store = FakeScenarioDefinitionStore()
    session_store = FakeScenarioSessionStore()
    conversation_store = FakeConversationStore()
    service = ScenarioTransferService(
        scenario_definition_store=definition_store,
        scenario_session_store=session_store,
        conversation_store=conversation_store,
    )
    return service, definition_store, session_store, conversation_store


@pytest.mark.asyncio
async def test_import_directory_upserts_curated_scenarios(tmp_path: Path) -> None:
    import json

    (tmp_path / "vault.json").write_text(
        json.dumps(
            {
                "id": "vault",
                "owner_id": str(SYSTEM_OWNER_ID),
                "name": "Vault",
                "description": "",
            }
        ),
        encoding="utf-8",
    )
    service, definition_store, _, _ = _service()

    report = await service.import_directory(tmp_path)

    assert report.imported == 1
    assert report.skipped == 0
    assert "vault" in definition_store.items


@pytest.mark.asyncio
async def test_import_scenario_payload_validates_and_saves() -> None:
    service, definition_store, _, _ = _service()
    payload = {
        "id": "vault",
        "owner_id": str(SYSTEM_OWNER_ID),
        "name": "Vault",
        "description": "",
    }

    scenario = await service.import_scenario_payload(payload)

    assert scenario is not None
    assert definition_store.items["vault"].name == "Vault"


@pytest.mark.asyncio
async def test_import_scenario_payload_rejects_invalid_payload() -> None:
    service, definition_store, _, _ = _service()

    scenario = await service.import_scenario_payload({"id": "vault"})

    assert scenario is None
    assert definition_store.items == {}


@pytest.mark.asyncio
async def test_export_scenario_round_trips() -> None:
    service, definition_store, _, _ = _service()
    original = ScenarioDefinition.create(
        scenario_id="vault", owner_id=SYSTEM_OWNER_ID, name="Vault", description="A vault."
    )
    await definition_store.save(original)

    payload = await service.export_scenario("vault")

    assert payload == scenario_definition_to_payload(original)


@pytest.mark.asyncio
async def test_export_scenario_missing_returns_none() -> None:
    service, _, _, _ = _service()
    assert await service.export_scenario("nope") is None


@pytest.mark.asyncio
async def test_session_export_import_round_trips_transcript() -> None:
    service, _, session_store, conversation_store = _service()
    session = ScenarioSession.create_for_user(
        scenario_definition_id="vault", user_id=USER_ID
    )
    await session_store.save(session)
    memory_key = MemoryKey(f"session_{session.id}")
    await conversation_store.save_message(
        memory_key, ConversationMessage(role=ConversationRole.CHARACTER, content="Opening.")
    )

    exported = await service.export_session(session.id)
    assert exported is not None
    assert exported["transcript"] == [
        {"role": "character", "content": "Opening.", "metadata": {}}
    ]

    other_session_store = FakeScenarioSessionStore()
    other_conversation_store = FakeConversationStore()
    restore_service = ScenarioTransferService(
        scenario_definition_store=FakeScenarioDefinitionStore(),
        scenario_session_store=other_session_store,
        conversation_store=other_conversation_store,
    )

    restored = await restore_service.import_session(exported)

    assert restored is not None
    assert restored.id == session.id
    restored_history = await other_conversation_store.load_messages(memory_key)
    assert restored_history == [
        ConversationMessage(role=ConversationRole.CHARACTER, content="Opening.")
    ]
