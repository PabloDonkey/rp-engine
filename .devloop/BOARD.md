# RP Engine — Dev Board

## 🔵 Backlog

### **S015** · User persona capture on new session start (+ `/clear`) — `/play` on a **new** user session (groups skipped, for now) prompts "provide a name + description/likes/dislikes for your character, or /skip" before showing the story intro; first line = name, rest = description; immutable once set; `{{user}}` resolves to the persona name (falls back to Telegram username on `/skip`). Needs a new pending-reply mechanism in the Telegram adapter (none exists today) + an immutable persisted field + migration. **Now also owns `/clear`** per **ADR-025**: `/restart` preserves player-owned settings (persona, language, rules), `/clear` resets them — which is what makes "immutable once set" survivable, so it isn't a follow-up. Also fixes the pre-existing orphaned-session hazard (`find_by_definition` has no `ORDER BY`). Design decisions locked, ready to implement. → [epic](epics/S015-user-persona-capture.md)

### **S011** · Admin panel — ops dashboard — landing overview: active sessions, DB health (reuses S007 `/health`), recent LLM latency/errors. Read-only. Follows S009. → [epic](epics/S011-admin-ops-dashboard.md)

### Activate StoryGraph / scenario branching — `StoryGraph`+`StoryBeat` exist as inert data; nothing drives beats yet. _(bare card — gets an S### when promoted to an epic)_ → see `../docs/DOMAIN_MODEL.md`


## 🟡 Up Next

_(nothing queued — see Backlog)_

## 🟢 In Progress

### **S014** · Session directives — Director Mode, Scenario Rules, Language preference — `/director <instruction>` (one-turn, auto-cleared by the generation that consumes it), `/rule add|remove <id>`/`/rules` (persistent, never-reused rule ids), `/language <code>` (persistent). New `SessionDirectives` value object on `ScenarioSession`, stored in a dedicated `scenario_sessions.directives` JSONB column (migration 0008, verified reversible against the real dev DB with 13 live sessions). New prompt sections in `ConversationBuilder`: Language → Scenario Rules → Director Instructions, after Response Format and before the memory hint; empty sections omitted. Admin panel session detail shows all three read-only. 319 passed, mypy + ruff + frontend build clean (2026-07-26). Remaining: live-verify over Telegram. → [epic](epics/S014-session-directives.md)

### **S012** · Admin panel — thinking trace + per-message debug menu — captures model "thinking"/reasoning content (was discarded by the LM Studio provider), stamps turn number onto each stored message, and replaces the transcript's global "Show generation traces" toggle with a per-message filter row (Thinking / Raw trace / System prompt / Turn metadata checkboxes, independent per message). Backend + frontend built, pytest/mypy/ruff/typecheck/build all clean, end-to-end data flow verified against a real (temp-dir) JSON backend with only the raw LLM call stubbed (2026-07-24). Remaining: exercise a real thinking-capable LM Studio model, browser eyeball. Follows S009. → [epic](epics/S012-transcript-thinking-and-per-message-debug-menu.md)

### **S009** · Admin panel — session/conversation debugging (MVP) — Vue SPA + JSON admin API on FastAPI, backend + core flow built and live-verified against real Postgres data (2026-07-24). Users → sessions → transcript + generation traces; delete session; block/unblock user. No auth (Tailscale trust). Remaining: browser/phone eyeball check, static-serve wiring, tests, ADR — see epic. → [epic](epics/S009-admin-panel-session-debugging.md)

## ✅ Done (recent)

### **S013 · 2026-07-26 · Retire JSON persistence backend** — Postgres is now the sole runtime backend (ADR-024): all 6 JSON stores deleted, `PlaythroughService` reads scenarios from `ScenarioDefinitionStore` directly, the JSON catalog loader recycled into `ScenarioTransferService` (import/export), tests get a testcontainers-backed Postgres fixture (`uv run pytest` needs zero manual setup). 254 passed, mypy + ruff clean. Live-verified against a real dev Postgres. → [archive](archive/S013-2026-07-26-retire-json-persistence.md)

### **S010 · 2026-07-26 · Admin panel — scenario catalog management** — landed together with S013 (which it depended on). Scenario CRUD (`GET/POST/PUT /admin/scenarios`, `POST /admin/scenarios/import`) + session export/import, all sharing one validation path via `ScenarioTransferService`. Frontend: scenario list/detail/edit pages (raw-JSON-textarea editor, the epic's own MVP bar) + a session-export button on S009's session detail page. Live-verified: panel-created/edited scenarios are immediately playable through `PlaythroughService`. → [archive](archive/S010-2026-07-26-admin-scenario-catalog-mgmt.md)

### **S007 · 2026-07-23 · DB startup health probe + `/health`** — `PostgresHealthProbe` (`ping` + schema-version drift warning) wired into lifespan via a protocol (no SQLAlchemy leak); fails fast by default on unreachable DB (`RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST`); `/health` gained `db`. Live-verified: real boot shows `available`; a forced one-step downgrade fired the drift warning without blocking startup. 221 passed / 12 skipped, mypy + ruff clean. → [archive](archive/S007-2026-07-23-db-startup-health-probe.md)


### **S006 · 2026-07-23 · Migration-vs-model integrity tests** — Upgrade/downgrade round-trip, autogenerate drift guard, migrate-then-contract fixture running all 7 store contracts against a real-migration schema; single-head check. **Caught a real bug**: `GenerationTraceRecord.session_id` had `index=True` with no matching migration index — fixed. Live PG 12/12 passed. → [archive](archive/S006-2026-07-23-migration-integrity-tests.md)


### **S005 · 2026-07-23 · Conversation store contract (both backends)** — Shared `conversation_store_contract.py` run against JSON (unit) + PG (gated integration, live-verified); PG-only tests for created_at tie-break + `session_id` population. Found metadata "non-str key" filtering is unreachable dead code (JSON-object semantics coerce keys to str first). → [archive](archive/S005-2026-07-23-conversation-store-contract.md)


### **S004 · 2026-07-23 · PG parity for identity + trace stores** — `PostgresUserIdentityStore`/`PostgresGroupIdentityStore`/`PostgresGenerationTraceStore` + migration 0007; wired into `build_container`'s postgres branch; shared `identity_serialization.py`; contract tests (JSON + gated PG). Live-verified: caught + fixed a flush-order FK bug. → [archive](archive/S004-2026-07-23-pg-identity-trace-stores.md)


<!-- Trimmed 2026-07-23: S001-S003 and the unlabeled 2026-07-22 access-control card are still
     in archive/ with full detail; removed here to keep this column glanceable. -->

### **S008** · Remove legacy WorldStore + DB docs refresh — delete the unwired character-era `WorldStore` port/impl/test + orphaned `default_world_id`; rewrite character-centric `DATABASE_MODEL.md`. **Note (2026-07-23): mis-filed here — checklist is still all unchecked and the code is still present; not actually done.** → [epic](epics/S008-remove-worldstore-docs.md)


