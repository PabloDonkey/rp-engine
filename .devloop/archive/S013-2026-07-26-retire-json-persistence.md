> 🗄️ **ARCHIVED — COMPLETED 2026-07-26.** Frozen; do not edit. Kept as evolution history.
> **Result:** Postgres is now the sole persistence backend (ADR-024). All 6 JSON store impls
> deleted; `PlaythroughService` reads scenarios from `ScenarioDefinitionStore` directly (was
> reading a JSON `ScenarioCatalog`); the catalog loader is recycled into
> `ScenarioTransferService` (import/export for scenarios + sessions), wired into both the admin
> panel (S010) and a boot-time curated-scenario import. Tests get a testcontainers-backed
> Postgres fixture — `uv run pytest` needs zero manual setup. 254 passed, mypy clean on `src/`,
> ruff clean. Live-verified end to end against a real dev Postgres: admin-created/edited
> scenarios are immediately playable, export/import round-trips byte-identical, all synthetic
> data cleaned up afterward.

# S013 · Retire JSON persistence backend

**Status:** ✅ COMPLETE — archived 2026-07-26
**Effort:** ~2-3 days
**Risk:** Medium (touches the composition root and every store call site; a fresh DB with no
import step means `/play` regresses to empty)

## Context

See **ADR-024** (`docs/DECISIONS.md`) for the full decision and rationale. Short version:
the Postgres migration (S001–S008) is done, `RP_ENGINE_PERSISTENCE_BACKEND` still defaults to
`"json"`, and the JSON/Postgres dual-backend setup left `PlaythroughService` reading scenarios
from an in-memory `ScenarioCatalog` (loaded from JSON at boot) rather than from
`ScenarioDefinitionStore` — which is why S010's "where do edits live" question didn't have a
clean answer. Postgres becomes the sole persistence backend; the JSON catalog code is
recycled into an import/export utility instead of deleted outright.

## Tasks

### Rewire the live scenario source
- [x] `PlaythroughService`: replace `self._catalog.list()` / `.get()` in `list_scenarios`,
      `start`, and `restart` with `scenario_definition_store.find_by_owner(SYSTEM_OWNER_ID)`
      / `.get_by_id(...)`. Drop the `catalog` constructor parameter entirely.
- [x] `app/main.py`: drop the `ScenarioCatalog.from_directories(...)` wiring into
      `PlaythroughService`; drop `settings.scenario_catalog_dirs` if nothing else reads it.
      (Kept `scenario_catalog_dirs` — repurposed as the import-source config for
      `ScenarioTransferService`.)

### Delete the JSON store backend
- [x] Delete `infrastructure/storage/json_scenario_definition_store.py`,
      `json_scenario_session_store.py`, `json_conversation_store.py`,
      `json_user_identity_store.py`, `json_group_identity_store.py`,
      `json_generation_trace_store.py` and their tests.
- [x] `config/settings.py`: remove `persistence_backend` (`Literal["json", "postgres"]`).
- [x] `app/main.py::build_container`: remove the `if settings.persistence_backend ==
      "postgres" / else` branch; wire the Postgres stores unconditionally. (Also simplified
      `AppContainer.db_health_probe` from `PostgresHealthProbe | None` to non-optional, since
      it's now always constructed — removed the dead `"n/a"` `/health` branch with it.)
- [x] Sweep for any other `persistence_backend` / `Json*Store` references (docs, `.env.example`,
      CLAUDE.md, README, DATABASE_MODEL.md, SCENARIOS.md, Makefile). Also deleted the two
      one-time migration scripts (`migrate_json_to_postgres.py`, `migrate_telegram_history.py`)
      whose imports would otherwise break.

### Import/export utility (must land before or alongside the deletion above)
- [x] Repurposed `infrastructure/catalog/scenario_catalog.py` → `infrastructure/scenario_transfer.py`
      (`read_scenario_directory`, `SYSTEM_OWNER_ID`).
- [x] New `application/services/scenario_transfer_service.py`: `import_directory`,
      `import_scenario_payload`, `export_scenario`, `export_session`, `import_session` — all
      reuse `scenario_serialization.py`'s existing both-directions helpers (only a small new
      `ConversationMessage` payload helper was needed).
- [x] Extended to `ScenarioSession` + its conversation transcript.
- [x] Exposed as admin panel endpoints (S010): `GET/POST/PUT /admin/scenarios`,
      `POST /admin/scenarios/import`, `GET /admin/sessions/{id}/export`,
      `POST /admin/sessions/import`.
- [x] Wired into `app/lifespan.py`: curated scenarios are imported (upsert, idempotent) on
      every boot, guarded so it only runs when the DB health check just passed — otherwise it
      would raise its own unhandled connection error right after that check already logged the
      same problem.

### Test infrastructure
- [x] Added `testcontainers[postgres]` (`testcontainers.community.postgres`, non-deprecated
      module); session-scoped `postgres_config` fixture in `tests/conftest.py` starts one
      container for the whole test session and runs `Base.metadata.create_all` once.
- [x] Deleted the JSON leg of the shared contract-test suite; the 3 non-migration Postgres
      contract-test files now consume the shared fixture and lost their `skipif` gate.
- [x] `test_migration_integrity_postgres.py` keeps its **own dedicated** container (module-scoped
      `migration_postgres_config`) since it drops/recreates the `public` schema around real
      Alembic upgrade/downgrade cycles — sharing the other fixture's pre-built schema would have
      let one suite stomp on the other. Also discovered and fixed: `alembic/env.py` builds its
      own `Settings()` from environment variables regardless of what's passed to
      `command.upgrade`/`downgrade`, so pointing Alembic at the testcontainers instance required
      `monkeypatch.setenv` on the `RP_ENGINE_POSTGRES_*` vars, not just constructing a
      `PostgresConfig`.
- [x] Deleted `scripts/test_postgres.sh` (redundant); updated CLAUDE.md/README/Makefile.

## Verification
- [x] `uv run pytest` green (254 passed) with zero manual setup, `uv run mypy src/` clean,
      `uv run ruff check .` clean.
- [x] Fresh-ish real Postgres (docker-compose, 0 rows in scenario tables) → booted the real app
      → `/health` reported `db: available` → `/admin/scenarios` listed all 6 curated scenarios
      from **both** configured catalog directories (proving the multi-directory loop and the
      boot-time import both work against a real DB, not just the test fixture).
- [x] `grep -rn "persistence_backend\|Json.*Store\|ScenarioCatalog" src/` returns only the
      historical docstring in `scenario_transfer.py` and the untouched, out-of-scope
      `json_world_store.py` (tracked separately by S008).

### Live end-to-end verification (2026-07-26, against the real dev Postgres, synthetic data cleaned up after)
- Created a scenario via `POST /admin/scenarios` (id `zz-verify-s013-s010`) → immediately visible
  via `PlaythroughService.list_scenarios()` and playable via `PlaythroughService.start()` (the
  exact code path `/play` in Telegram uses) — proves Postgres is genuinely the live source, not
  just reachable through the admin API.
- Edited it via `PUT`; the *edited* name flowed through to a freshly-started playthrough.
- Guardrails confirmed: 409 on duplicate create, 400 on PUT id-mismatch, 404 on missing-scenario
  PUT, 422 on a payload that fails `scenario_definition_from_payload`.
- Exported the scenario, re-imported via `POST /admin/scenarios/import`, diffed — byte-identical.
- Started a synthetic session, exported it (`GET /admin/sessions/{id}/export`), deleted it,
  restored it via `POST /admin/sessions/import` — transcript round-tripped correctly.
- All synthetic scenario/session data deleted afterward; confirmed the real catalog (6
  scenarios) was untouched.
- Not verified: an actual Telegram client sending `/play zz-verify...` (no bot token available
  in this environment) — the in-process `PlaythroughService` call exercises the identical code
  path the Telegram adapter calls, so this is considered equivalent coverage.
