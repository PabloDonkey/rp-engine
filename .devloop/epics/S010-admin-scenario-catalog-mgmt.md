# S010 · Admin panel — scenario catalog management

**Status:** 🔵 Backlog (follow-up to [S009](S009-admin-panel-session-debugging.md); blocked on
[S013](S013-retire-json-persistence.md))
**Effort:** ~2 days
**Risk:** Medium (writes the live scenario source; a bad edit breaks scenario loading)

## Context

Second slice of the admin panel (see S009 for the product/interview decisions). Today
`ScenarioDefinition`s are curated **JSON files** loaded by `infrastructure/catalog/`
(`ScenarioCatalog`). Authoring/editing means hand-editing JSON. This epic lets the operator
**list / view / create / edit** scenario definitions from the panel — the user flagged
scenario-catalog editing as a wanted write action.

Depends on S009's frontend scaffold + admin API pattern being in place, **and on S013**
rewiring `PlaythroughService` to read scenarios from `ScenarioDefinitionStore` instead of the
JSON `ScenarioCatalog` — until that lands, a scenario saved via this panel would not actually
be playable through `/play`.

## Resolved: source of truth for edits (2026-07-24, see ADR-024)

**`ScenarioDefinitionStore` (Postgres) is authoritative.** The admin panel is the only place
scenarios are authored/edited going forward. JSON is no longer a live source — it's the
format used by the S013 import/export utility (bulk-seed a fresh DB, or export a stored
scenario for backup/portability). Validation reuses the shared serializer
(`infrastructure/scenario_serialization.py`) so a panel-authored scenario round-trips
identically to an imported one.

## Tasks
- [ ] Confirm S013 has landed (`PlaythroughService` reads from `ScenarioDefinitionStore`,
      JSON stores removed) before starting UI work.
- [ ] `GET /admin/scenarios` + `GET /admin/scenarios/{id}` read endpoints.
- [ ] `POST`/`PUT /admin/scenarios` write endpoints, validated through the shared serializer.
- [ ] Frontend: scenario list, detail/view, and an editor (world, characters, rules, opening).
      A structured form beats a raw JSON textarea if time allows; raw-JSON-with-validation is an
      acceptable MVP.
- [ ] Guardrails: validate before save; never persist a scenario that fails to deserialize.

## Verification
- [ ] Backend suite green (mypy/ruff/pytest); a scenario created via the panel loads through the
      normal catalog path and can start a playthrough.
- [ ] Live-verify: create/edit a scenario in the panel, then start it from Telegram.
