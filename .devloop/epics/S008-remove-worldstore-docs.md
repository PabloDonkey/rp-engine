# S008 · Remove legacy WorldStore + DB docs refresh

**Status:** 🔵 Backlog
**Effort:** ~1-2 h
**Risk:** Low (pure deletion of unwired code + docs)

## Context

`WorldStore` is **dead legacy from the character-centric era** (pre-ADR-023). In the
scenario-native model, world data lives embedded in `ScenarioDefinition.world` (JSONB) — there
is no standalone world entity. The port is **never wired** in `build_container` (no JSON *or* PG
impl is selected), so nothing in the running app touches it. **Decision (2026-07-23): remove it**,
rather than give it PG parity.

Confirmed self-contained reference surface (grep, excl. generated egg-info):

- `core/ports/world_store.py` — the `WorldStore` Protocol
- `core/ports/__init__.py` — import + `__all__` entry
- `infrastructure/storage/json_world_store.py` — `JsonWorldStore` impl
- `infrastructure/storage/__init__.py` — import + `__all__` entry
- `tests/unit/infrastructure/test_json_world_store.py` — its only test
- `infrastructure/config/settings.py` — orphaned `default_world_id` field + `validate_default_world_id`
  validator (feeds no wired store) → also remove, plus its `.env.example` / README mention

Also stale: `docs/DATABASE_MODEL.md` still describes the character-centric "Milestone 1/2" scope
and removed `sessions`/`characters` tables.

## Tasks

- [ ] **Delete the port** — `core/ports/world_store.py`; drop the import + `"WorldStore"` from
      `core/ports/__init__.py`.
- [ ] **Delete the JSON impl** — `infrastructure/storage/json_world_store.py`; drop the import +
      `"JsonWorldStore"` from `infrastructure/storage/__init__.py`.
- [ ] **Delete the test** — `tests/unit/infrastructure/test_json_world_store.py`.
- [ ] **Drop the orphaned setting** — remove `default_world_id` + `validate_default_world_id` from
      `settings.py`; remove `RP_ENGINE_DEFAULT_WORLD_ID` from `.env.example` and the README env table
      (verify it's referenced nowhere else in `src/` first).
- [ ] **Note it** — one line in `docs/DECISIONS.md` (or a footnote under ADR-023) recording the
      WorldStore removal as scenario-pivot cleanup.
- [ ] **Rewrite `docs/DATABASE_MODEL.md`** for the scenario-centric final state: live tables only
      (`scenario_definitions`, `scenario_sessions`, `active_scenario_sessions`, `conversation_messages`,
      + S004's identity/trace tables), backend selection, and the shared-serializer parity model.
- [ ] **Review/retire `scripts/migrate_telegram_history.py`** — confirm it targets the scenario model
      and selected backend, or retire it if legacy.

## Verification

- [ ] `grep -rn "WorldStore\|world_store\|default_world_id" src/ tests/` returns nothing.
- [ ] `uv run pytest` green, `uv run mypy .` clean, `uv run ruff check .` clean.
- [ ] `DATABASE_MODEL.md` matches `models.py` + Alembic head; no character-centric residue.
