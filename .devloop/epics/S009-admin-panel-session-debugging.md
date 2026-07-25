# S009 · Admin panel — session/conversation debugging (MVP)

**Status:** 🔵 Backlog
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
- [ ] Decide the read surface and add an `AdminService` (application layer) that composes the
      existing stores; **no business logic in the router**.
- [ ] `GET /admin/users` — list known users (id, handle, session count, last activity).
- [ ] `GET /admin/users/{id}/sessions` — that user's scenario sessions (scenario, status,
      created/updated, message count).
- [ ] `GET /admin/sessions/{id}` — session detail: scenario ref, full conversation history.
- [ ] `GET /admin/sessions/{id}/traces` — generation traces for the session (prompt, model,
      params, output) so "why did it say that" is answerable.
- [ ] **Action:** `DELETE /admin/sessions/{id}` (delete) + reset variant — clear/reset a
      session via the session store. Confirm delete vs. reset semantics against the store API.
- [ ] **Action:** `POST /admin/users/{id}/block` + `/unblock` — mutate the Telegram allowlist
      via `TelegramAuthorization` (+ `persist()`), respecting the empty-allowlist=allow-all rule.
- [ ] Pydantic response models in `adapters/api/models.py`; wire the router in `app/main.py`.
- [ ] Bind admin routes to tailscale/localhost only (or document the deploy binding); **no auth
      middleware** by decision, but keep the router isolated so a passphrase can be added later.

### Frontend — Vue SPA (mirror tailflow stack)
- [ ] Scaffold `frontend/` (Vite + Vue 3 TS), copy tailflow's config shape (Tailwind v4 via
      `@tailwindcss/vite`, reka-ui, Pinia, vue-router, Zod, eslint/vitest/playwright).
- [ ] `src/api/` client with Zod-validated responses against the admin endpoints.
- [ ] Pinia stores: users, sessions, current-session detail.
- [ ] Pages: **Users list → User detail (sessions) → Session detail** (conversation transcript
      + traces panel). **Mobile-first layout** (used from phone over Tailscale).
- [ ] Wire the two write actions (delete/reset session, block/unblock user) with a confirm step.
- [ ] Dev proxy to FastAPI; production build served as static by the app (or documented separately).

### Glue / docs
- [ ] `Makefile` targets: run admin frontend dev server; build; run app with admin API.
- [ ] ADR in `docs/DECISIONS.md`: admin panel exists, **no-auth-over-tailscale** trust model,
      Vue-SPA + JSON-API shape, why not server-rendered.
- [ ] Note follow-ups: S010 (catalog mgmt incl. scenario edit), S011 (ops dashboard).

## Verification

- [ ] `uv run pytest` green, `uv run mypy .` clean, `uv run ruff check .` clean (backend).
- [ ] Frontend `typecheck` + `test` green; at least one Playwright happy-path (open a session,
      see transcript + traces).
- [ ] **Live-verify** end-to-end against a real running app over the tailnet, **including from
      phone**: browse a real user → session → transcript + traces; delete/reset a throwaway
      session; block then unblock a test user and confirm the allowlist file changed.
