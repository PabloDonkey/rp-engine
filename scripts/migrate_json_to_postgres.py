# ruff: noqa: E402
"""One-time migration: copy the JSON-backed persistence into Postgres.

Scope is exactly the storage ports selected by RP_ENGINE_PERSISTENCE_BACKEND: scenario
definitions, scenario sessions (+ the active-session-per-owner index), conversation
messages, generation traces, user identities, and group identities.

Left untouched — not part of the backend switch, or dead data nothing reads anymore:
  - data/catalog/                    curated scenario JSON, always loaded fresh from disk
  - data/characters/, data/feedback/ static feedback-message templates, always JSON
  - data/telegram/                   TelegramAuthorization / TelegramNarratorStore, JSON-only
  - data/worlds/                     unwired legacy WorldStore (pending removal, see S008)
  - data/memory/                     pre-scenario-pivot artifact; no current code reads it
  - data/sessions/*/session.json     pre-ADR-023 character-centric Session records,
                                      superseded by data/scenario_sessions/*/session.json

Usage:
    uv run alembic upgrade head
    uv run python scripts/migrate_json_to_postgres.py [--data-dir data] [--dry-run]

The target connection comes from the usual RP_ENGINE_POSTGRES_* settings / .env.

Idempotency: scenario definitions/sessions upsert by id, and the active-session index
upserts by owner — safe to re-run. User/group identities skip an id already present in
Postgres. Conversation messages and generation traces are append-only in Postgres, so
re-running against a target that already has them duplicates those rows.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.memory.models import MemoryKey
from rp_engine.core.scenario.scenario_session import SessionOwnerKind
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.identity_serialization import identity_from_payload
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import (
    ConversationMessageRecord,
    GenerationTraceRecord,
    GroupIdentityRecord,
    GroupRecord,
    UserIdentityRecord,
    UserRecord,
)
from rp_engine.infrastructure.postgres.transaction import session_scope
from rp_engine.infrastructure.scenario_serialization import (
    scenario_definition_from_payload,
    scenario_session_from_payload,
)
from rp_engine.infrastructure.storage.json_conversation_store import JsonConversationStore

logger = logging.getLogger("migrate_json_to_postgres")


@dataclass(slots=True)
class MigrationReport:
    scenario_definitions: int = 0
    scenario_sessions: int = 0
    active_sessions: int = 0
    conversation_messages: int = 0
    generation_traces: int = 0
    users: int = 0
    groups: int = 0
    skipped: list[str] = field(default_factory=list)


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def _iter_subdirs(path: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    return sorted(entry for entry in path.iterdir() if entry.is_dir())


async def _migrate_scenario_definitions(
    data_dir: Path,
    store: PostgresScenarioDefinitionStore,
    report: MigrationReport,
    *,
    dry_run: bool,
) -> None:
    for entry in _iter_subdirs(data_dir / "scenarios"):
        definition_file = entry / "definition.json"
        if not definition_file.exists():
            continue
        scenario = scenario_definition_from_payload(_read_json(definition_file))
        if scenario is None:
            report.skipped.append(f"scenario definition {entry.name}: unparseable")
            continue
        if not dry_run:
            await store.save(scenario)
        report.scenario_definitions += 1


async def _migrate_scenario_sessions(
    data_dir: Path,
    store: PostgresScenarioSessionStore,
    report: MigrationReport,
    *,
    dry_run: bool,
) -> None:
    sessions_dir = data_dir / "scenario_sessions"
    for entry in _iter_subdirs(sessions_dir):
        session_file = entry / "session.json"
        if not session_file.exists():
            continue
        session = scenario_session_from_payload(_read_json(session_file))
        if session is None:
            report.skipped.append(f"scenario session {entry.name}: unparseable")
            continue
        if not dry_run:
            await store.save(session)
        report.scenario_sessions += 1

    active_file = sessions_dir / "active_by_owner.json"
    if not active_file.exists():
        return
    for key, raw_session_id in _read_json(active_file).items():
        owner_kind, _, owner_id = key.partition(":")
        if owner_kind not in ("user", "group") or not owner_id or not isinstance(
            raw_session_id, str
        ):
            report.skipped.append(f"active-session index entry {key!r}: malformed")
            continue
        try:
            owner_uuid = UUID(owner_id)
            session_uuid = UUID(raw_session_id)
        except ValueError:
            report.skipped.append(f"active-session index entry {key!r}: bad uuid")
            continue
        if not dry_run:
            kind: SessionOwnerKind = "user" if owner_kind == "user" else "group"
            await store.set_active_for_owner(
                owner_kind=kind, owner_id=owner_uuid, session_id=session_uuid
            )
        report.active_sessions += 1


def _parse_trace_timestamp(record: dict[str, object]) -> datetime | None:
    raw = record.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


async def _migrate_conversations_and_traces(
    data_dir: Path,
    session_factory: async_sessionmaker[AsyncSession],
    report: MigrationReport,
    *,
    dry_run: bool,
) -> None:
    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        return
    json_store = JsonConversationStore(base_path=sessions_dir)

    for entry in _iter_subdirs(sessions_dir):
        try:
            session_uuid: UUID | None = UUID(entry.name)
        except ValueError:
            session_uuid = None

        history_file = entry / "history.jsonl"
        if history_file.exists():
            memory_key = MemoryKey(f"session_{entry.name}")
            messages = await json_store.load_messages(memory_key)
            if messages:
                # history.jsonl carries no per-message timestamp; synthesize strictly
                # increasing ones (ending at the file's mtime) so PG's created_at-then-id
                # ordering reproduces the original chat order instead of shuffling on
                # whatever random id each row gets.
                end_time = datetime.fromtimestamp(history_file.stat().st_mtime, tz=UTC)
                base_time = end_time - timedelta(milliseconds=len(messages))
                if not dry_run:
                    async with session_scope(session_factory) as db_session:
                        for index, message in enumerate(messages):
                            db_session.add(
                                ConversationMessageRecord(
                                    id=uuid4(),
                                    memory_key=memory_key.value,
                                    session_id=session_uuid,
                                    role=message.role.value,
                                    content=message.content,
                                    payload_metadata=message.metadata,
                                    created_at=base_time + timedelta(milliseconds=index),
                                )
                            )
                report.conversation_messages += len(messages)

        trace_file = entry / "trace.jsonl"
        if trace_file.exists() and session_uuid is not None:
            records: list[dict[str, object]] = []
            with trace_file.open("r", encoding="utf-8") as file:
                for line in file:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        loaded = json.loads(stripped)
                    except json.JSONDecodeError:
                        report.skipped.append(f"trace line in {entry.name}: invalid json")
                        continue
                    if isinstance(loaded, dict):
                        records.append(loaded)
            if records and not dry_run:
                async with session_scope(session_factory) as db_session:
                    for index, record in enumerate(records):
                        created_at = _parse_trace_timestamp(record) or datetime.now(UTC)
                        db_session.add(
                            GenerationTraceRecord(
                                id=uuid4(),
                                session_id=session_uuid,
                                record=record,
                                created_at=created_at + timedelta(microseconds=index),
                            )
                        )
            report.generation_traces += len(records)
        elif trace_file.exists():
            report.skipped.append(f"trace file in {entry.name}: directory name is not a uuid")


async def _migrate_users(
    data_dir: Path,
    session_factory: async_sessionmaker[AsyncSession],
    report: MigrationReport,
    *,
    dry_run: bool,
) -> None:
    for entry in _iter_subdirs(data_dir / "users"):
        profile_file = entry / "profile.json"
        identities_file = entry / "identities.json"
        if not profile_file.exists() or not identities_file.exists():
            continue

        profile = _read_json(profile_file)
        raw_id = profile.get("id")
        display_name = profile.get("display_name")
        if not isinstance(raw_id, str) or not isinstance(display_name, str):
            report.skipped.append(f"user {entry.name}: malformed profile.json")
            continue
        try:
            user_id = UUID(raw_id)
        except ValueError:
            report.skipped.append(f"user {entry.name}: id is not a uuid")
            continue

        identities_map = _read_json(identities_file).get("identities")
        identities: list[tuple[str, str, dict[str, str]]] = []
        if isinstance(identities_map, dict):
            for provider, raw in identities_map.items():
                if not isinstance(provider, str) or not isinstance(raw, dict):
                    continue
                parsed = identity_from_payload(raw)
                if parsed is not None:
                    identities.append((provider, parsed[0], parsed[1]))

        if dry_run:
            report.users += 1
            continue

        async with session_factory() as db_session:
            existing = await db_session.get(UserRecord, user_id)
        if existing is not None:
            continue

        async with session_scope(session_factory) as db_session:
            db_session.add(UserRecord(id=user_id, display_name=display_name))
            # UserRecord/UserIdentityRecord have no ORM relationship, so flush order
            # isn't otherwise guaranteed — the identity rows' FK needs the user first.
            await db_session.flush()
            for provider, external_id, metadata in identities:
                db_session.add(
                    UserIdentityRecord(
                        provider=provider,
                        external_id=external_id,
                        user_id=user_id,
                        identity_metadata=metadata,
                    )
                )
        report.users += 1


async def _migrate_groups(
    data_dir: Path,
    session_factory: async_sessionmaker[AsyncSession],
    report: MigrationReport,
    *,
    dry_run: bool,
) -> None:
    for entry in _iter_subdirs(data_dir / "groups"):
        profile_file = entry / "profile.json"
        identities_file = entry / "identities.json"
        if not profile_file.exists() or not identities_file.exists():
            continue

        profile = _read_json(profile_file)
        raw_id = profile.get("id")
        display_name = profile.get("display_name")
        if not isinstance(raw_id, str) or not isinstance(display_name, str):
            report.skipped.append(f"group {entry.name}: malformed profile.json")
            continue
        try:
            group_id = UUID(raw_id)
        except ValueError:
            report.skipped.append(f"group {entry.name}: id is not a uuid")
            continue

        identities_map = _read_json(identities_file).get("identities")
        identities: list[tuple[str, str, dict[str, str]]] = []
        if isinstance(identities_map, dict):
            for provider, raw in identities_map.items():
                if not isinstance(provider, str) or not isinstance(raw, dict):
                    continue
                parsed = identity_from_payload(raw)
                if parsed is not None:
                    identities.append((provider, parsed[0], parsed[1]))

        if dry_run:
            report.groups += 1
            continue

        async with session_factory() as db_session:
            existing = await db_session.get(GroupRecord, group_id)
        if existing is not None:
            continue

        async with session_scope(session_factory) as db_session:
            db_session.add(GroupRecord(id=group_id, display_name=display_name))
            await db_session.flush()
            for provider, external_id, metadata in identities:
                db_session.add(
                    GroupIdentityRecord(
                        provider=provider,
                        external_id=external_id,
                        group_id=group_id,
                        identity_metadata=metadata,
                    )
                )
        report.groups += 1


async def _run(data_dir: Path, *, dry_run: bool) -> MigrationReport:
    report = MigrationReport()
    settings = Settings(persistence_backend="postgres")
    config = PostgresConfig.from_settings(settings)
    engine = create_engine(config)
    session_factory = create_session_factory(engine)

    if not dry_run:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            await engine.dispose()
            raise SystemExit(
                f"Cannot reach Postgres with the current RP_ENGINE_POSTGRES_* settings: {exc}"
            ) from exc

    try:
        await _migrate_scenario_definitions(
            data_dir, PostgresScenarioDefinitionStore(session_factory), report, dry_run=dry_run
        )
        await _migrate_scenario_sessions(
            data_dir, PostgresScenarioSessionStore(session_factory), report, dry_run=dry_run
        )
        await _migrate_conversations_and_traces(
            data_dir, session_factory, report, dry_run=dry_run
        )
        await _migrate_users(data_dir, session_factory, report, dry_run=dry_run)
        await _migrate_groups(data_dir, session_factory, report, dry_run=dry_run)
    finally:
        await engine.dispose()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=Path("data"), type=Path)
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would move; write nothing."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-5.5s %(message)s")

    report = asyncio.run(_run(args.data_dir, dry_run=args.dry_run))

    label = "DRY RUN (nothing written)" if args.dry_run else "complete"
    logger.info("Migration %s", label)
    logger.info("  scenario definitions:   %d", report.scenario_definitions)
    logger.info("  scenario sessions:      %d", report.scenario_sessions)
    logger.info("  active-session entries: %d", report.active_sessions)
    logger.info("  conversation messages:  %d", report.conversation_messages)
    logger.info("  generation trace lines: %d", report.generation_traces)
    logger.info("  users:                  %d", report.users)
    logger.info("  groups:                 %d", report.groups)
    if report.skipped:
        logger.warning("Skipped %d item(s):", len(report.skipped))
        for item in report.skipped:
            logger.warning("  - %s", item)


if __name__ == "__main__":
    main()
