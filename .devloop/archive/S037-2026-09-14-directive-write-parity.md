> 🗄️ **ARCHIVED — COMPLETED 2026-09-14.** Frozen; do not edit. Kept as evolution history.
> **Result:** the admin panel's Directives tab is no longer read-only. `PUT
> /sessions/{id}/language`, `POST /sessions/{id}/rules`, `DELETE
> /sessions/{id}/rules/{rule_id}`, and `POST /sessions/{id}/director` wrap the same
> `SessionDirectives` mutators (`with_language`, `with_rule`, `without_rule`,
> `with_director_instruction`) `/language`, `/rule`, and `/director` already used on
> Telegram, so the validation is shared and only the transport differs. A session
> superseded by `/restart` or `/clear` is refused with 409, the same guard
> `set_session_persona` already applies. `SessionHeader.vue`'s Directives panel is now a
> form — a language `<select>`, add/remove rule rows, an add-director-note field — instead
> of a read-only `<dl>`.

# S037 · Directives write parity — director/rule/language from the panel

**Status:** ✅ COMPLETE — archived 2026-09-14
**Effort:** ~0.5 day
**Risk:** Low. No migration, no core port change, no new dependency —
`SessionDirectives`/`SessionDirectiveService` already own the validation
(`with_language`, `with_rule`, `without_rule`, `with_director_instruction`); this only
wires the existing domain calls onto the admin router and the panel, the same shape S031
used for turns and S015 used for persona.

## Context

The admin panel's Directives tab (S014) has always been read-only — a comment in
`SessionHeader.vue` said so directly: "directives are set by the player over Telegram
(/language, /rule, /director), the panel only reflects them." `/memory summary on|off`
broke that pattern already (S023 gave it a panel switch), so the remaining gap was
`/director`, `/rule add|remove`, and `/language`. Pablo asked for parity here directly
("next task is having the web interface in parity with the telegram command"); scope
was narrowed to directives-write via a clarifying question — session reset tiers
(`/restart`/`/clear`) were explicitly ruled out of this epic.

## Scope

- [x] `AdminService`: `set_session_language`, `add_session_rule`, `remove_session_rule`,
  `add_session_director_instruction` — each fetches the session, calls the matching
  `SessionDirectives` mutator, saves, returns the updated `ScenarioSession` (`None` when
  the session is missing; `remove_session_rule` raises `ValueError` when the id doesn't
  match any rule, mirroring `/rule remove`'s own reply).
- [x] `admin_models.py`: `AdminSessionLanguageRequest`, `AdminSessionRuleRequest`,
  `AdminSessionDirectorInstructionRequest`; dropped the "read-only" claim from
  `AdminSessionDirectivesResponse`'s docstring.
- [x] `admin_routes.py`: `PUT /sessions/{id}/language`, `POST /sessions/{id}/rules`,
  `DELETE /sessions/{id}/rules/{rule_id}`, `POST /sessions/{id}/director` — each maps a
  `ValueError` to 400 (404 for the rule-not-found case on the delete route), 404 for a
  missing session, and returns `AdminSessionResponse`. **Added beyond the original scope
  note**, for correctness parity with `set_session_persona`: a 409 refusal when the
  session is already superseded by `/restart` or `/clear`, since nothing written there
  would ever reach a prompt again (`_require_live_session_for_write`, shared by all four
  routes). The shared `_directive_response` helper takes a *callable*, not an
  already-built coroutine — passing a live coroutine would construct it before the
  liveness guard runs, which is harmless in production but caused a real
  "coroutine was never awaited" warning under test.
- [x] Frontend: zod-typed `api.setSessionLanguage`/`addSessionRule`/`removeSessionRule`/
  `addSessionDirectorInstruction`; matching `admin` store actions; `SessionHeader.vue`'s
  Directives panel became a form (language `<select>` from a client-side mirror of
  `SUPPORTED_LANGUAGES`, add/remove rule rows, an add-director-note field) instead of a
  `<dl>`, following the same "editable on the live session, read-only once superseded"
  split S015 gave Persona.
- [x] Docs: `CLAUDE.md`'s and `docs/ARCHITECTURE.md`'s "directive commands... stay
  Telegram-only" lines corrected to describe the new routes and the 409/400/404 mapping.

## Out of scope

- `/restart` and `/clear` (session reset tiers) — a separate, larger epic (different
  risk shape: resets touch persona *and* memory, not just directives). Still
  Telegram-only after this epic.
- A manual "clear the director queue" panel action — Telegram has no such command
  either (the queue only clears itself, consumed by the next generation), so there was no
  parity gap to close here.
- Streaming, cancel, authentication — unrelated, already out of scope per S031/S036.

## Verification

- [x] Backend: `uv run pytest` — 865 passed, 1 pre-existing failure unrelated to this
  change (`test_reads_bundled_catalog` needs the gitignored, locally-seeded
  `data/catalog/` directory, absent from a fresh worktree checkout — the same gap S036's
  epic recorded). `uv run ruff check .` and `uv run mypy .` clean on every touched file
  (pre-existing, unrelated errors remain in `benchmark/` scripts and one
  `generation_trace_store.py` line, same as S036 reported).
- [x] Frontend: `npm run typecheck` clean, `npm run test` — 95 passed (6 new, for the
  store actions). `npm run build`'s `vue-tsc -b` step fails on the same pre-existing
  `LorebookSection.test.ts` issue S036's epic recorded, unrelated to this change.
- **Known gap:** no in-browser click-through (no browser-automation tool available this
  session) — same limitation earlier admin-panel epics (S009, S010, S031, S036) recorded.
