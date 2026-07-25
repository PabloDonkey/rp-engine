# S009 · Admin panel — session/conversation debugging (MVP)

**Status:** 🟢 In Progress — backend + core frontend flow built and live-verified against real
Postgres data (2026-07-24); remaining work is polish/hardening, see notes below.
**Effort:** ~2-3 days
**Risk:** Medium (new adapter surface + first frontend in the repo; write actions touch live user state)

## Context

DB migration to Postgres is done (S004-S007). The bot now has real persisted state
(users, scenario sessions, conversations, generation traces) but **no way to inspect it**
except reading the DB by hand. This epic stands up the **first slice of an admin panel**
whose primary job is **debugging live sessions**: "why did the bot say that / why is this
session stuck."

**Product decisions (2026-07-24, interview):**
- **Operator:** just the owner (Pablo), reached over **Tailscale**, including **from phone**.
- **Auth:** **none** — trust the tailnet. Panel binds to the tailscale interface / localhost;
  no login, no accounts. (Defense-in-depth passphrase deferred; note in DECISIONS.)
- **Read + limited actions.** MVP write actions: **delete/reset a session** and
  **block/unblock a user**. (Scenario-catalog editing is its own epic → S010.)
- **Frontend:** a **Vue SPA**, mirroring the `~/projects/tailflow/frontend` stack:
  Vue 3 + TS + Vite + Pinia + vue-router + Tailwind v4 + reka-ui, Zod for API schemas,
  Vitest + Playwright. Hits a **JSON admin API** added to the existing FastAPI app.

Blocking a user = removing them from the Telegram allowlist
(`adapters/telegram/authorization.py`, `users.json`). There is **no separate blocklist**;
"block" means removing from `allowed_user_ids` (and empty allowlist = allow-all, so note the
semantics carefully before exposing a toggle). Confirm the intended behavior before shipping.

## Architecture fit

Keep the core framework-free. Admin read/write use-cases go through
`application/services/` (new `AdminService` or extend existing services), which depend only
on ports (`ScenarioSessionStore`, `ConversationStore`, `GenerationTraceStore`,
`UserIdentityStore`, …). New JSON routes live in `adapters/api/` alongside the existing
`/chat` router. Frontend is a sibling top-level `frontend/` (or `admin/`) dir, dev-proxied
to the API and built to static assets served by FastAPI in prod.

## Tasks

### Backend — admin JSON API (`adapters/api/`)
- [x] `AdminService` (`application/services/admin_service.py`) composing the existing ports;
      no business logic in the router. Required extending two ports with read methods that
      didn't exist yet — `UserIdentityStore.list_users()` and
      `GenerationTraceStore.list_for_session()` — implemented + contract-tested for **both**
      JSON and Postgres backends (dual-persistence parity rule).
- [x] `GET /admin/users` — id, display_name, telegram_external_id, session_count, is_blocked.
- [x] `GET /admin/users/{id}/sessions`
- [x] `GET /admin/sessions/{id}` (includes message_count) + `GET /admin/sessions/{id}/transcript`
      + `GET /admin/sessions/{id}/traces`
- [x] **Action:** `DELETE /admin/sessions/{id}` — deletes the session row and clears its
      conversation messages. (No separate "reset" variant — delete covers the need; a fresh
      session is created by starting a new playthrough.)
- [x] **Action:** `POST /admin/users/{id}/block` + `/unblock` — mutate `TelegramAuthorization`'s
      allowlist directly (`remove_private_user`/`add_private_user` + `persist()`). Note: the
      empty-allowlist=allow-all footgun flagged in this doc was actually fixed **before** this
      epic started (separate fail-closed change, 2026-07-24: empty allowlist now denies all
      except the configured admin) — `is_blocked` in the API reflects explicit-allowlist
      membership via `has_explicit_private_user`.
- [x] Pydantic models in `adapters/api/admin_models.py`; router wired in `app/main.py` via
      `create_admin_router(admin_service, telegram_authorization)`.
- [x] No auth middleware, router isolated (`create_admin_router` takes deps explicitly so a
      passphrase layer can wrap it later). Added permissive CORS (`allow_origins=["*"]`) so the
      Vite dev server / any tailnet origin can call it — consistent with the no-auth trust model.
      **Not yet done:** binding admin routes to the tailscale interface specifically (currently
      bound wherever the app binds, per `RP_ENGINE_APP_HOST`) — see Known gaps below.

### Frontend — Vue SPA
- [x] Scaffolded `frontend/` (Vite + Vue 3 + TS + Pinia + vue-router + Tailwind v4 + Zod).
      **Deviation from the original plan:** dropped `reka-ui`, `motion-v`, ESLint, and the
      Vitest/Playwright test harness to fit the session's scope — native `confirm()` for
      destructive-action guards instead of a modal component, no component/e2e tests yet.
      Everything else (state mgmt, routing, schema validation, Tailwind) matches tailflow.
- [x] `src/api/index.ts` — fetch client, Zod-parsed responses, typed `ApiError`.
- [x] `src/stores/admin.ts` — single Pinia store: users, user-sessions, session-detail
      (transcript + traces), loading/error state per slice.
- [x] Pages: `UsersPage` → `UserSessionsPage` → `SessionDetailPage` (transcript + collapsible
      raw-JSON traces). Mobile-first (single column, large tap targets).
- [x] Both write actions wired with a `confirm()` guard: delete session, block/unblock user.
- [x] Dev proxy `/admin` → `http://localhost:8000` in `vite.config.ts`. Production static-build
      serving from FastAPI **not wired yet** — currently dev-server only (see Known gaps).

### Glue / docs
- [ ] `Makefile` targets for the frontend (dev/build) — not done.
- [ ] ADR in `docs/DECISIONS.md` for the admin panel trust model / stack choice — not done.
- [x] Follow-ups already filed: S010 (catalog mgmt), S011 (ops dashboard).

## Known gaps (deliberately deferred, not oversights)

- No component/e2e test coverage on the frontend (typecheck + production build both verified
  clean instead).
- No static-file serving of the built frontend from FastAPI — today you run `npm run dev`
  and the app separately; there's no single deployable artifact yet.
- Admin routes aren't bound/restricted to the tailscale interface specifically — anything
  that can reach the app's bound host:port can hit `/admin/*`, matching the app's existing
  bind behavior rather than adding new restriction.
- `reka-ui`/`motion-v` (tailflow's component/animation libs) weren't pulled in; the UI is
  plain Tailwind + native elements.

## Verification

- [x] `uv run pytest` green (243 passed, 12 skipped), `uv run mypy .` clean (no new errors vs.
      the pre-existing baseline), `uv run ruff check .` clean (backend).
- [x] Frontend `typecheck` (`vue-tsc --noEmit`) and production `build` both clean. No automated
      test suite exists yet (see Known gaps) — no Playwright happy-path.
- [x] **Live-verified** end-to-end against the real Postgres database (2026-07-24): inserted
      disposable synthetic rows (a `__verify_test_user__`, a session, a message, a trace),
      confirmed via curl through both the raw API and the Vite dev-server proxy that
      users/sessions/transcript/traces all render correctly against real data (10 real users
      + the synthetic one all listed correctly with real session counts); block → unblock
      round-tripped and persisted to the allowlist file correctly; delete removed both the
      session row and its conversation messages. All synthetic rows cleaned up afterward — the
      live Telegram bot process (already running on :8000) was left untouched throughout by
      running verification on a separate port (:8099) with Telegram disabled.
      **Not done:** actual browser/phone verification — no browser-automation tool was
      available in this session, so the UI's visual rendering was never eyeballed, only its
      data flow (proxying, API contracts, Zod parsing implied by successful build).
