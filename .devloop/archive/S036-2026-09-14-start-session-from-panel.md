> 🗄️ **ARCHIVED — COMPLETED 2026-09-14.** Frozen; do not edit. Kept as evolution history.
> **Result:** the panel can now start a playthrough for an existing user, not just play one
> that already exists. `POST /admin/users/{user_id}/sessions` wraps the same
> `PlaythroughService.start(...)` call `/play` makes, plus `set_persona(...)` when the call
> began a genuinely new session and a persona name was given — one web form asking for the
> scenario and the persona at once, so none of Telegram's `TelegramPendingPersonaStore`
> multi-turn state machine comes along. A new `StartSessionPage.vue` (scenario select +
> optional persona name/description) reached from a "Start new session" link on
> `UserSessionsPage.vue`, landing on the existing session page on success.

# S036 · Start a new story from the panel

**Status:** ✅ COMPLETE — archived 2026-09-14
**Effort:** ~0.5 day
**Risk:** Low. No migration, no core port change, no new dependency — a thin route over
`PlaythroughService`, which already does everything `/play` needs (S031 proved the same
pattern for turn routes).

## Context

Promoted from the standing backlog card left by S031: *"S031 plays sessions that already
exist; it cannot create one. Needs a scenario picker and the persona form (a web form asks
for name and description at once, so none of Telegram's `TelegramPendingPersonaStore` state
machine comes along). Clean slice on its own."*

## Scope

- [x] `AdminStartSessionRequest` (`scenario_id`, optional `persona_name`/`persona_description`)
  and `AdminPlaythroughStartResponse` (session + opening + `resumed`) in `admin_models.py`.
- [x] `POST /admin/users/{user_id}/sessions` on the admin router: 404 if the user or the
  scenario is missing; calls `PlaythroughService.start`, then `set_persona` only when the
  session is genuinely new (`resumed is False`) and a persona name was given. A resumed
  session's persona fields are ignored — an existing session keeps whatever persona it
  already has, exactly as `/play` behaves on Telegram.
- [x] `container.playthrough_service` wired into `create_admin_router` in `app/main.py`.
- [x] Frontend: `PlaythroughStart` zod schema + `api.startSession(...)`, an `admin` store
  action (`startSessionBusy`/`startSessionError`, kept apart from `actionError` — a failed
  start has nothing to do with an open session's turn/persona errors), and
  `StartSessionPage.vue` (scenario `<select>` + optional persona fields) at
  `/users/:userId/sessions/new`, linked from `UserSessionsPage.vue`.
- [x] Docs: `CLAUDE.md`'s "starting one... stay Telegram-only" line corrected;
  `docs/ARCHITECTURE.md`'s S031 section extended with the new route.

## Verification

- [x] Backend: `uv run pytest` — 839 passed, 1 pre-existing failure unrelated to this change
  (`test_reads_bundled_catalog` needs the gitignored, locally-seeded `data/catalog/`
  directory, absent from a fresh worktree checkout — confirmed present on `main` before this
  change too). `uv run ruff check` and `uv run mypy` clean on every touched file (one
  pre-existing `mypy` error in `generation_trace_store.py`, confirmed unrelated).
- [x] Frontend: `npm run typecheck` clean, `npm run test` — 89 passed (2 new, for the store
  action). `npm run build`'s `vue-tsc -b` step fails on a pre-existing issue in
  `LorebookSection.test.ts` from the S024 lorebook commit, unrelated to this change.
- **Known gap:** no in-browser click-through (no browser-automation tool available this
  session) — same limitation earlier admin-panel epics (S009, S010, S031) recorded.

## Out of scope

- **Creating a new `User`.** The picker starts a session for a user who already exists (has
  at least one Telegram identity); the panel has no user-creation flow and this epic does
  not add one.
- **Streaming, cancel, rules/language/director as play controls, authentication.** Same
  exclusions S031 already made; nothing here changes them.
