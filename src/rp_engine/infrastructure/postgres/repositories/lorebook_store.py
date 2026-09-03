import re
from typing import cast

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.lorebook_store import LorebookStore
from rp_engine.core.scenario.lore_entry import LoreEntry, LoreEntryPriority
from rp_engine.infrastructure.postgres.models import LoreEntryRecord
from rp_engine.infrastructure.postgres.transaction import session_scope

# Anything that is not a letter, digit or space breaks `to_tsquery`'s `word1 & word2`
# syntax (an apostrophe, a hyphen). Triggers are short phrases a person typed, so
# stripping punctuation before building the expression is enough; nothing here needs to
# survive a round trip back into a trigger key.
_NON_WORD = re.compile(r"[^\w\s]+")

_PRIORITY_RANK = case(
    (LoreEntryRecord.priority == "high", 2),
    (LoreEntryRecord.priority == "normal", 1),
    else_=0,
)


def _trigger_query_expr(trigger_keys: tuple[str, ...]) -> str:
    """Build the `to_tsquery` source text from a set of trigger phrases.

    Each phrase becomes an AND'd group of its own words (`hurting & someone`);
    phrases are OR'd together. Stored as plain text rather than a `tsquery`-typed
    column so no SQLAlchemy `TSQUERY` type is needed — it is cast at query time.
    """
    groups = []
    for phrase in trigger_keys:
        words = _NON_WORD.sub(" ", phrase).split()
        if not words:
            continue
        groups.append("(" + " & ".join(words) + ")")
    return " | ".join(groups)


_VALID_PRIORITIES: frozenset[str] = frozenset(("low", "normal", "high"))


def _to_domain(record: LoreEntryRecord) -> LoreEntry:
    priority: LoreEntryPriority = (
        cast(LoreEntryPriority, record.priority)
        if record.priority in _VALID_PRIORITIES
        else "normal"
    )
    return LoreEntry(
        id=record.id,
        scenario_definition_id=record.scenario_definition_id,
        title=record.title,
        content=record.content,
        trigger_keys=tuple(record.trigger_keys),
        priority=priority,
        related_entry_ids=tuple(record.related_entry_ids),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class PostgresLorebookStore(LorebookStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_matching(
        self, scenario_definition_id: str, recall_text: str, *, limit: int
    ) -> tuple[LoreEntry, ...]:
        recall_vector = func.to_tsvector("english", recall_text)
        trigger_query = func.to_tsquery("english", LoreEntryRecord.trigger_query_expr)
        rank = func.ts_rank(recall_vector, trigger_query)
        statement = (
            select(LoreEntryRecord)
            .where(
                LoreEntryRecord.scenario_definition_id == scenario_definition_id,
                LoreEntryRecord.trigger_query_expr != "",
                recall_vector.op("@@")(trigger_query),
            )
            .order_by(rank.desc(), _PRIORITY_RANK.desc())
            .limit(limit)
        )
        async with self._session_factory() as db_session:
            records = (await db_session.scalars(statement)).all()
        return tuple(_to_domain(record) for record in records)

    async def list_for_scenario(self, scenario_definition_id: str) -> tuple[LoreEntry, ...]:
        statement = (
            select(LoreEntryRecord)
            .where(LoreEntryRecord.scenario_definition_id == scenario_definition_id)
            .order_by(LoreEntryRecord.title)
        )
        async with self._session_factory() as db_session:
            records = (await db_session.scalars(statement)).all()
        return tuple(_to_domain(record) for record in records)

    async def get(self, scenario_definition_id: str, entry_id: str) -> LoreEntry | None:
        statement = select(LoreEntryRecord).where(
            LoreEntryRecord.scenario_definition_id == scenario_definition_id,
            LoreEntryRecord.id == entry_id,
        )
        async with self._session_factory() as db_session:
            record = await db_session.scalar(statement)
        return _to_domain(record) if record is not None else None

    async def save(self, entry: LoreEntry) -> LoreEntry:
        values = {
            "scenario_definition_id": entry.scenario_definition_id,
            "id": entry.id,
            "title": entry.title,
            "content": entry.content,
            "trigger_keys": list(entry.trigger_keys),
            "trigger_query_expr": _trigger_query_expr(entry.trigger_keys),
            "priority": entry.priority,
            "related_entry_ids": list(entry.related_entry_ids),
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }
        statement = insert(LoreEntryRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[LoreEntryRecord.scenario_definition_id, LoreEntryRecord.id],
            set_={
                "title": values["title"],
                "content": values["content"],
                "trigger_keys": values["trigger_keys"],
                "trigger_query_expr": values["trigger_query_expr"],
                "priority": values["priority"],
                "related_entry_ids": values["related_entry_ids"],
                "updated_at": values["updated_at"],
            },
        )
        async with session_scope(self._session_factory) as db_session:
            await db_session.execute(statement)
        return entry

    async def delete(self, scenario_definition_id: str, entry_id: str) -> None:
        statement = select(LoreEntryRecord).where(
            LoreEntryRecord.scenario_definition_id == scenario_definition_id,
            LoreEntryRecord.id == entry_id,
        )
        async with session_scope(self._session_factory) as db_session:
            record = await db_session.scalar(statement)
            if record is not None:
                await db_session.delete(record)
