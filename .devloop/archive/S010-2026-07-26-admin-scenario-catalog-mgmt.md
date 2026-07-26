> 🗄️ **ARCHIVED — COMPLETED 2026-07-26.** Frozen; do not edit. Kept as evolution history.
> **Result:** Admin panel scenario CRUD, landed together with S013 (which it depended on).
> Backend: `GET/POST/PUT /admin/scenarios`, `POST /admin/scenarios/import`,
> `GET /admin/sessions/{id}/export` + `POST /admin/sessions/import`, all routed through
> `ScenarioTransferService` so panel writes and JSON import share one validation path.
> Frontend: `ScenariosPage`/`ScenarioDetailPage`/`ScenarioEditPage` (raw-JSON-textarea editor,
> the epic's own stated MVP bar) + an Export button added to S009's `SessionDetailPage`.
> Live-verified: a scenario created/edited via the panel is immediately playable through
> `PlaythroughService` — proving the panel is genuinely wired to the live source, not a side
> channel. See S013's archive entry for the full verification transcript.

# S010 · Admin panel — scenario catalog management

**Status:** ✅ COMPLETE — archived 2026-07-26
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
- [x] Confirm S013 has landed (`PlaythroughService` reads from `ScenarioDefinitionStore`,
      JSON stores removed) before starting UI work.
- [x] `GET /admin/scenarios` + `GET /admin/scenarios/{id}` read endpoints.
- [x] `POST`/`PUT /admin/scenarios` write endpoints, validated through the shared serializer
      (via `ScenarioTransferService.import_scenario_payload`, shared with the S013 import path).
      Also added `POST /admin/scenarios/import` (upsert, no existence check — for
      bulk/paste-JSON import) and `GET/POST /admin/sessions/.../export`/`import` per ADR-024's
      session-transfer scope.
- [x] Frontend: scenario list (`ScenariosPage.vue`), detail/view (`ScenarioDetailPage.vue` +
      Export button), and an editor (`ScenarioEditPage.vue`, shared between create/edit).
      Took the epic's explicit MVP escape hatch — **raw-JSON-textarea editor with server-side
      validation**, not a structured form — given the scope also covered S013 in the same pass.
      Also added an Export button to the existing (S009) `SessionDetailPage.vue` for session
      backup, per ADR-024.
- [x] Guardrails: create returns 409 on an existing id, edit returns 404 if the id doesn't exist
      and 400 if the body's `id` doesn't match the URL, both return 422 (never persisting) on a
      payload that fails `scenario_definition_from_payload`.

## Verification
- [x] Backend suite green (254 passed, mypy clean on `src/`, ruff clean); frontend `vue-tsc`
      typecheck and `vite build` both clean.
- [x] Live-verify (2026-07-26, real dev Postgres, synthetic data cleaned up after): created a
      scenario via `POST /admin/scenarios`, confirmed it was immediately listed by and playable
      through `PlaythroughService` (the code path `/play` in Telegram uses) — proving the panel
      writes to the actual live source, not a side channel. Edited it via `PUT`; the edit was
      reflected in a freshly-started playthrough. Verified all four guardrail status codes
      (409/400/404/422). Exported and re-imported the scenario — byte-identical. See S013's
      archived epic for the full verification transcript (shared session, both epics landed
      together).
- Known gap: no in-browser/phone eyeball of the new pages (no browser-automation tool
  available this session, matching the same limitation noted for S009's original pass) —
  `vite build`/`vue-tsc` clean is as far as this pass verified the frontend.
