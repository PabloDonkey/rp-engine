# S010 · Admin panel — scenario catalog management

**Status:** 🔵 Backlog (follow-up to [S009](S009-admin-panel-session-debugging.md))
**Effort:** ~2 days
**Risk:** Medium (writes to the curated catalog; a bad edit breaks scenario loading)

## Context

Second slice of the admin panel (see S009 for the product/interview decisions). Today
`ScenarioDefinition`s are curated **JSON files** loaded by `infrastructure/catalog/`
(`ScenarioCatalog`). Authoring/editing means hand-editing JSON. This epic lets the operator
**list / view / create / edit** scenario definitions from the panel — the user flagged
scenario-catalog editing as a wanted write action.

Depends on S009's frontend scaffold + admin API pattern being in place.

## Open questions to resolve first
- **Source of truth for edits:** the catalog JSON files, or a DB-backed `ScenarioDefinitionStore`?
  (The port exists; decide whether edited scenarios live in Postgres vs. writing back JSON.)
  This is the central design decision for the epic — resolve before building UI.
- Validation: reuse the shared serializer (`infrastructure/scenario_serialization.py`) so a
  panel-authored scenario round-trips identically to a file-authored one.

## Tasks
- [ ] Decide + document the edit-target (JSON files vs. `ScenarioDefinitionStore`); ADR if it
      changes the persistence story.
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
