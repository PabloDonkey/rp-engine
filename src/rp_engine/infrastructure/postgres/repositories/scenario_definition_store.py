from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.infrastructure.postgres.models import ScenarioDefinitionRecord
from rp_engine.infrastructure.postgres.transaction import session_scope
from rp_engine.infrastructure.scenario_serialization import (
    characters_to_payload,
    scenario_definition_from_payload,
    story_graph_to_payload,
    world_to_payload,
)


class PostgresScenarioDefinitionStore(ScenarioDefinitionStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, scenario_id: str) -> ScenarioDefinition | None:
        statement = select(ScenarioDefinitionRecord).where(
            ScenarioDefinitionRecord.id == scenario_id
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def find_by_owner(self, owner_id: UUID) -> list[ScenarioDefinition]:
        statement = select(ScenarioDefinitionRecord).where(
            ScenarioDefinitionRecord.owner_id == owner_id
        )
        async with self._session_factory() as db_session:
            records = (await db_session.scalars(statement)).all()
        return [
            scenario for record in records if (scenario := self._to_domain(record)) is not None
        ]

    async def save(self, scenario: ScenarioDefinition) -> None:
        values = {
            "id": scenario.id,
            "owner_id": scenario.owner_id,
            "name": scenario.name,
            "description": scenario.description,
            "world": world_to_payload(scenario.world),
            "characters": characters_to_payload(scenario.characters),
            "rules": list(scenario.rules),
            "story_graph": story_graph_to_payload(scenario.story_graph),
            "initial_context": scenario.initial_context,
            "visibility": scenario.visibility.value,
            "allowed_group_chat_ids": list(scenario.allowed_group_chat_ids),
            "payload_metadata": dict(scenario.metadata),
        }
        statement = insert(ScenarioDefinitionRecord).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[ScenarioDefinitionRecord.id],
            set_={
                "owner_id": statement.excluded.owner_id,
                "name": statement.excluded.name,
                "description": statement.excluded.description,
                "world": statement.excluded.world,
                "characters": statement.excluded.characters,
                "rules": statement.excluded.rules,
                "story_graph": statement.excluded.story_graph,
                "initial_context": statement.excluded.initial_context,
                "visibility": statement.excluded.visibility,
                "allowed_group_chat_ids": statement.excluded.allowed_group_chat_ids,
                "metadata": statement.excluded.metadata,
            },
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    async def delete(self, scenario_id: str) -> None:
        statement = delete(ScenarioDefinitionRecord).where(
            ScenarioDefinitionRecord.id == scenario_id
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    @staticmethod
    def _to_domain(record: ScenarioDefinitionRecord | None) -> ScenarioDefinition | None:
        if record is None:
            return None
        payload = {
            "id": record.id,
            "owner_id": str(record.owner_id),
            "name": record.name,
            "description": record.description,
            "world": record.world,
            "characters": record.characters or {},
            "rules": record.rules or [],
            "story_graph": record.story_graph,
            "initial_context": record.initial_context,
            "visibility": record.visibility or "PUBLIC",
            "allowed_group_chat_ids": record.allowed_group_chat_ids or [],
            "metadata": record.payload_metadata or {},
        }
        return scenario_definition_from_payload(payload)
