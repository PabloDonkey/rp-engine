# S008 · WorldStore resolution + DB docs refresh

**Status:** 🔵 Backlog
**Effort:** ~1-2 h
**Risk:** Low

## Context

Two loose ends around the PG migration that aren't code-parity but block "done":

1. **`WorldStore` is a dangling port.** `core/ports/world_store.py` + `JsonWorldStore` exist,
   but `build_container` **never wires a WorldStore** (JSON or PG) — world data lives embedded
   in `ScenarioDefinition.world` JSONB. The port is effectively dead. Decide and act:
   *deprecate/remove it* (preferred, since world is embedded) **or** give it real JSON+PG parity.
2. **`docs/DATABASE_MODEL.md` is stale.** It still describes the character-centric
   "Milestone 1/2" scope, lists removed `sessions`/`characters` tables as the model, and
   claims WorldStore/identity/trace "remain on JSON in this milestone" — contradicting the
   scenario pivot (ADR-023) and the S004 parity work.
3. **`scripts/migrate_telegram_history.py`** — confirm it targets the scenario model and the
   selected backend, or retire it if legacy.

## Tasks

- [ ] Decide WorldStore fate; if removing, delete port + JSON impl + exports and note in an ADR.
- [ ] Rewrite `docs/DATABASE_MODEL.md` for the scenario-centric final state: live tables
      (`scenario_definitions`, `scenario_sessions`, `active_scenario_sessions`,
      `conversation_messages`, + S004's identity/trace tables), backend selection, parity model.
- [ ] Review/retire `migrate_telegram_history.py`.

## Verification

- [ ] `grep` shows no live references to a removed WorldStore; mypy + ruff clean.
- [ ] DATABASE_MODEL.md matches `models.py` + Alembic head; no character-centric residue.
