# S013 · Retire JSON persistence backend

**Status:** 🔵 Backlog (blocks [S010](S010-admin-scenario-catalog-mgmt.md))
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
- [ ] `PlaythroughService`: replace `self._catalog.list()` / `.get()` in `list_scenarios`,
      `start`, and `restart` with `scenario_definition_store.find_by_owner(SYSTEM_OWNER_ID)`
      / `.get_by_id(...)`. Drop the `catalog` constructor parameter entirely.
- [ ] `app/main.py`: drop the `ScenarioCatalog.from_directories(...)` wiring into
      `PlaythroughService`; drop `settings.scenario_catalog_dirs` if nothing else reads it.

### Delete the JSON store backend
- [ ] Delete `infrastructure/storage/json_scenario_definition_store.py`,
      `json_scenario_session_store.py`, `json_conversation_store.py`,
      `json_user_identity_store.py`, `json_group_identity_store.py`,
      `json_generation_trace_store.py` and their tests.
- [ ] `config/settings.py`: remove `persistence_backend` (`Literal["json", "postgres"]`).
- [ ] `app/main.py::build_container`: remove the `if settings.persistence_backend ==
      "postgres" / else` branch; wire the Postgres stores unconditionally.
- [ ] Sweep for any other `persistence_backend` / `Json*Store` references (docs, `.env.example`,
      CLAUDE.md's "backend from `RP_ENGINE_PERSISTENCE_BACKEND`" line, `app/main.py`'s health
      payload at `persistence_backend`).

### Import/export utility (must land before or alongside the deletion above)
- [ ] Repurpose `infrastructure/catalog/scenario_catalog.py`'s directory-walk/validation logic
      into an import path: JSON scenario payload → `scenario_definition_from_payload` (shared
      serializer, unchanged) → `ScenarioDefinitionStore.save`.
- [ ] Add the export counterpart: stored `ScenarioDefinition` → same JSON shape, for backup /
      portability.
- [ ] Extend both directions to `ScenarioSession` (+ its conversation transcript via
      `ConversationStore`), so a playthrough can be backed up/restored, not just curated
      scenarios.
- [ ] Expose import/export as admin panel endpoints/buttons (per ADR-024; ties into the S009
      admin API and frontend, informs S010's editor UI).
- [ ] One-time run: import the existing curated catalog JSON into Postgres so `/play` isn't
      empty on the first Postgres-only boot. Confirm against a real (or staging) DB before the
      JSON stores are deleted.

### Test infrastructure
- [ ] Add an auto-managed Postgres fixture (testcontainers or equivalent) so `uv run pytest`
      needs no manual `docker compose up`.
- [ ] Delete the JSON leg of the shared contract-test suite (`tests/.../contracts/`); the
      Postgres contract run becomes the default, ungated suite.
- [ ] Keep (or fold in) whatever real-migration-only tests (S006) the managed fixture can't
      replace.
- [ ] Update CLAUDE.md's Commands section — `uv run pytest` no longer means "JSON backend, PG
      tests skip."

## Verification
- [ ] `uv run pytest` green with zero manual setup (managed Postgres fixture), `uv run mypy .`
      clean, `uv run ruff check .` clean.
- [ ] Fresh DB (migrations only, no data) + import step → `/scenarios` in Telegram lists the
      curated set, `/play <id>` works end to end.
- [ ] `grep -r` for `persistence_backend`, `Json.*Store`, `ScenarioCatalog` in `src/` and
      `app/main.py` turns up only the repurposed import/export code.
