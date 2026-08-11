from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind
from rp_engine.infrastructure.postgres.models import (
    ActiveScenarioSessionRecord,
    ScenarioSessionRecord,
)
from rp_engine.infrastructure.postgres.transaction import session_scope
from rp_engine.infrastructure.scenario_serialization import (
    memory_settings_to_payload,
    scenario_session_from_payload,
    session_directives_to_payload,
)

# Key the memory settings live under inside the `directives` JSONB column. See
# `_player_state_payload`.
MEMORY_PAYLOAD_KEY = "memory"


class PostgresScenarioSessionStore(ScenarioSessionStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, session_id: UUID) -> ScenarioSession | None:
        statement = select(ScenarioSessionRecord).where(ScenarioSessionRecord.id == session_id)
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def find_by_owner(
        self,
        owner_kind: str,
        owner_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> list[ScenarioSession]:
        statement = select(ScenarioSessionRecord).where(
            ScenarioSessionRecord.owner_kind == owner_kind,
            ScenarioSessionRecord.owner_id == owner_id,
        )
        if not include_deleted:
            statement = statement.where(ScenarioSessionRecord.deleted_at.is_(None))
        statement = statement.order_by(ScenarioSessionRecord.created_at.desc())
        async with self._session_factory() as db_session:
            records = (await db_session.scalars(statement)).all()
        return [session for record in records if (session := self._to_domain(record)) is not None]

    async def find_by_definition(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_definition_id: str,
    ) -> ScenarioSession | None:
        # `deleted_at IS NULL` is what makes this "the current session" rather than "some
        # session that once ran this scenario" — without it a reset leaves its predecessor
        # behind and `/play <same id>` could resurrect the pre-reset transcript. The
        # ORDER BY is belt-and-braces: if two live rows ever coexist, pick deterministically.
        statement = (
            select(ScenarioSessionRecord)
            .where(
                ScenarioSessionRecord.owner_kind == owner_kind,
                ScenarioSessionRecord.owner_id == owner_id,
                ScenarioSessionRecord.scenario_definition_id == scenario_definition_id,
                ScenarioSessionRecord.deleted_at.is_(None),
            )
            .order_by(ScenarioSessionRecord.created_at.desc())
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    async def save(self, session: ScenarioSession) -> ScenarioSession:
        # Stamped here rather than by callers: `save()` is the one place every write passes
        # through, so `updated_at` cannot go stale by someone forgetting to touch it.
        # (SQLAlchemy's `onupdate=` would not fire — this writes via ON CONFLICT DO UPDATE.)
        stamped = replace(session, updated_at=datetime.now(UTC))
        values = {
            "id": stamped.id,
            "scenario_definition_id": stamped.scenario_definition_id,
            "owner_kind": stamped.owner_kind,
            "owner_id": stamped.owner_id,
            "active_participants": dict(stamped.active_participants),
            "world_state": dict(stamped.world_state),
            "story_progress": dict(stamped.story_progress),
            "created_at": stamped.created_at,
            "updated_at": stamped.updated_at,
            "deleted_at": stamped.deleted_at,
            "payload_metadata": dict(stamped.metadata),
            "directives": _player_state_payload(stamped),
            "user_persona_name": stamped.user_persona_name,
            "user_persona_description": stamped.user_persona_description,
        }
        statement = insert(ScenarioSessionRecord).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[ScenarioSessionRecord.id],
            # `created_at` is deliberately absent: it is a lifecycle fact set once at
            # insert, not something a later save may rewrite.
            set_={
                "scenario_definition_id": statement.excluded.scenario_definition_id,
                "owner_kind": statement.excluded.owner_kind,
                "owner_id": statement.excluded.owner_id,
                "active_participants": statement.excluded.active_participants,
                "world_state": statement.excluded.world_state,
                "story_progress": statement.excluded.story_progress,
                "updated_at": statement.excluded.updated_at,
                "deleted_at": statement.excluded.deleted_at,
                "metadata": statement.excluded.metadata,
                "directives": statement.excluded.directives,
                "user_persona_name": statement.excluded.user_persona_name,
                "user_persona_description": statement.excluded.user_persona_description,
            },
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)
        return stamped

    async def delete(self, session_id: UUID) -> None:
        statement = delete(ScenarioSessionRecord).where(ScenarioSessionRecord.id == session_id)
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    async def set_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session_id: UUID,
    ) -> None:
        statement = insert(ActiveScenarioSessionRecord).values(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=session_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[
                ActiveScenarioSessionRecord.owner_kind,
                ActiveScenarioSessionRecord.owner_id,
            ],
            set_={"session_id": statement.excluded.session_id},
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)

    async def get_active_for_owner(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        statement = (
            select(ScenarioSessionRecord)
            .join(
                ActiveScenarioSessionRecord,
                ActiveScenarioSessionRecord.session_id == ScenarioSessionRecord.id,
            )
            .where(
                ActiveScenarioSessionRecord.owner_kind == owner_kind,
                ActiveScenarioSessionRecord.owner_id == owner_id,
                # The active pointer is repointed on every reset, so this is a second line
                # of defence rather than the mechanism — but a stale pointer must never
                # hand the engine a superseded session.
                ScenarioSessionRecord.deleted_at.is_(None),
            )
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: ScenarioSessionRecord | None) -> ScenarioSession | None:
        if record is None:
            return None
        payload = {
            "id": str(record.id),
            "scenario_definition_id": record.scenario_definition_id,
            "owner_kind": record.owner_kind,
            "owner_id": str(record.owner_id),
            "active_participants": record.active_participants or {},
            "world_state": record.world_state or {},
            "story_progress": record.story_progress or {},
            "created_at": _as_utc(record.created_at).isoformat(),
            "updated_at": _as_utc(record.updated_at).isoformat(),
            "deleted_at": (
                _as_utc(record.deleted_at).isoformat() if record.deleted_at is not None else None
            ),
            "metadata": record.payload_metadata or {},
            "directives": record.directives or {},
            "memory": (record.directives or {}).get(MEMORY_PAYLOAD_KEY),
            "user_persona_name": record.user_persona_name,
            "user_persona_description": record.user_persona_description,
        }
        return scenario_session_from_payload(payload)


def _player_state_payload(session: ScenarioSession) -> dict[str, object]:
    """Everything the player set for this session, in the one JSONB column that holds it.

    The memory settings ride inside the `directives` column rather than getting a column
    of their own (ADR-026: no new column). The two belong together: both are player-owned
    session state under the same ADR-025 reset tier, so `/restart` carries both and
    `/clear` resets both. A session written before S022 simply has no `memory` key, and
    reads back with the default layers.
    """
    return {
        **session_directives_to_payload(session.directives),
        MEMORY_PAYLOAD_KEY: memory_settings_to_payload(session.memory),
    }


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
