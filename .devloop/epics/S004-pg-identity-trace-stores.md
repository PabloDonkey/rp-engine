# S004 · PG parity for identity + generation-trace stores

**Status:** 🔵 Backlog
**Effort:** ~4-6 h
**Risk:** Medium (new tables + migration + serializer parity across two backends)

## Context

This is the **core gap** for "finishing the PG integration." Three ports still have **no
Postgres implementation**, so even with `RP_ENGINE_PERSISTENCE_BACKEND=postgres` the
composition root (`app/main.py` `build_container`) hard-wires JSON for them:

- `GenerationTraceStore` → `JsonGenerationTraceStore`
- `UserIdentityStore`     → `JsonUserIdentityStore`
- `GroupIdentityStore`    → `JsonGroupIdentityStore`

Result: a "postgres" deployment still reads/writes JSON files on local disk for traces and
identity mappings — the app is **not** actually single-backend and cannot run statelessly.

## Tasks

- [ ] **Models** — add SQLAlchemy records in `infrastructure/postgres/models.py`:
  - [ ] `user_identities` (external user id ↔ internal UUID + profile metadata)
  - [ ] `group_identities` (external group/chat id ↔ internal UUID + metadata)
  - [ ] `generation_traces` (trace id, session/memory key, prompt+response payload JSONB, created_at)
  - [ ] Match column names/nullability to the JSON serializer output.
- [ ] **Migration** — new reversible Alembic migration `0007_identity_trace_tables`
  - [ ] `create_table` for all three; indexes on external-id lookups.
  - [ ] Verify `upgrade head` **and** `downgrade` against a real DB (see S006).
- [ ] **Serializer parity** *(decided 2026-07-23: extend the shared serializer, not per-store
      native mapping)* — extend `infrastructure/scenario_serialization.py` (or a sibling shared
      serializer module) so JSON and PG round-trip **identical dicts** for each entity, keeping a
      single source of truth for the storage shape rather than two divergent code paths.
- [ ] **Postgres stores** — `PostgresUserIdentityStore`, `PostgresGroupIdentityStore`,
      `PostgresGenerationTraceStore` under `postgres/repositories/`, export in `repositories/__init__.py`.
- [ ] **Wire composition root** — in `build_container`, move these three into the
      `persistence_backend == "postgres"` branch alongside the scenario stores.
- [ ] **Contract tests** — shared contract module per entity, run against **both** JSON and PG
      (mirror the scenario-store pattern: unit JSON runner + gated integration PG runner).

## Verification

- [ ] `uv run pytest` green; `scripts/test_postgres.sh` green (new contracts pass on PG).
- [ ] `uv run mypy .` clean, `uv run ruff check .` clean.
- [ ] Manual: boot with `postgres` backend, confirm no new JSON files are written for
      traces/identities; rows land in the three new tables.
