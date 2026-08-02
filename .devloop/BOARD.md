# RP Engine — Dev Board

## 🔵 Backlog

### **S020** · `/director` notes silently overwrite instead of stacking — `SessionDirectives.director_instruction` is a single `str`; each `/director <instruction>` replaces it, so sending several before the next reply loses all but the last with no warning. Turn it into a tuple of notes: append per command, render all in the `[Director Instructions]` prompt block, clear as a unit on consume. Touches the domain object, builder, `scenario_serialization.py` (JSONB shape, no migration needed), the adapter's confirmation message, and the admin panel's read-only view. → [epic](epics/S020-director-instruction-stacking.md)

### **S019** · Use the SDK's `LlmReasoningParsing` instead of regexing an internal marker — the provider splits thinking from prose on `__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_<hex>__`, an internal synthetic marker with no compatibility promise. If it ever changes shape the regex stops matching and **the model's entire reasoning gets delivered to the player as the story**. The SDK exposes `reasoning_parsing` (`enabled`/`start_string`/`end_string`) on `LlmPredictionConfig` — declare the delimiters instead of reverse-engineering them, and fail loudly rather than passing an unsplit blob through as prose. Also gives S018 the exact markers if it needs to emit a closed think block. → [epic](epics/S019-lmstudio-reasoning-parsing.md)

### Admin panel — show superseded sessions — S016 left the *presentation* out of scope: the session list should render a muted "superseded" badge with `deleted_at`, sort newest-first, and `session_count` on the users list needs a deliberate call (live-only today, vs "3 live / 7 total" which is the more useful number for analysis). Backend is already done — `AdminService.list_user_sessions` passes `include_deleted=True` and the API returns `created_at`/`updated_at`/`deleted_at`. _(bare card — gets an S### if it grows)_ → see [S016](archive/S016-2026-07-27-session-soft-delete-lifecycle.md)

### **S011** · Admin panel — ops dashboard — landing overview: active sessions, DB health (reuses S007 `/health`), recent LLM latency/errors. Read-only. Follows S009. → [epic](epics/S011-admin-ops-dashboard.md)

### Activate StoryGraph / scenario branching — `StoryGraph`+`StoryBeat` exist as inert data; nothing drives beats yet. _(bare card — gets an S### when promoted to an epic)_ → see `../docs/DOMAIN_MODEL.md`


## 🟡 Up Next

_(nothing queued — see Backlog)_

## 🟢 In Progress

### **S012** · Admin panel — thinking trace + per-message debug menu — captures model "thinking"/reasoning content (was discarded by the LM Studio provider), stamps turn number onto each stored message, and replaces the transcript's global "Show generation traces" toggle with a per-message filter row (Thinking / Raw trace / System prompt / Turn metadata checkboxes, independent per message). Backend + frontend built, pytest/mypy/ruff/typecheck/build all clean, end-to-end data flow verified against a real (temp-dir) JSON backend with only the raw LLM call stubbed (2026-07-24). Remaining: exercise a real thinking-capable LM Studio model, browser eyeball. Follows S009. → [epic](epics/S012-transcript-thinking-and-per-message-debug-menu.md)

## ✅ Done (recent)

### **S015 · 2026-07-27 · User persona capture on new session start (+ `/clear`)** — `/play` on a new user session asks who you're playing before the story intro (first line = name, rest = description, `/skip` for the Telegram name); immutable once set; `{{user}}` resolves to it everywhere, including the opening line the player reads. New `[User Persona]` prompt section, `TelegramPendingPersonaStore`, two `scenario_sessions` columns (migration 0009). Implements **ADR-025**: `/restart` carries persona + language + rules forward and no longer re-prompts, `/clear confirm` resets them — one shared `_reset(carry_player_state=...)` path. Admin panel can set *and* edit a persona (ADR-025 amendment: `override_persona`, an operator exception the player-facing guard never sees). Live-verified over Telegram. → [archive](archive/S015-2026-07-27-user-persona-capture.md)

### **S016 · 2026-07-27 · Session lifecycle timestamps + soft delete** — **session resurrection closed.** `updated_at` + `deleted_at`; `deleted_at IS NULL` **is** "the current session"; `/restart` and `/clear` stamp the outgoing session instead of orphaning it, keeping its transcript readable. **Took two passes:** migration 0009 fixed the code and left the data broken — every pre-S016 orphan was still "live", so `/play <id>` still resurrected old stories. Live testing caught what a fake-store unit test could not. Migration **0010** backfills (one live session per owner+scenario; 13 live → 10 on the dev DB) and makes the partial index **unique** so it cannot recur. New `test_playthrough_reset_postgres.py` drives the real repositories. Admin presentation cut to a Backlog card. → [archive](archive/S016-2026-07-27-session-soft-delete-lifecycle.md)

### **S018 · 2026-07-27 · `/continue` by assistant prefill** — truncated replies now resume mid-sentence instead of re-planning. `/continue` no longer sends a "please continue" nudge (a new assistant turn, which triggers re-reasoning on reasoning models). Instead, `Conversation.continue_final_message` marks the intent, `build_resume` skips the directive turn, and the mapper leaves the chat assistant-final — triggering LM Studio's prefill. Probed live: mid-sentence continuation, in character, **no reasoning pass**, 45 tokens instead of 2000+ spent reasoning with no output. Removed the `<notes>` fallback. Requires S017. → [archive](archive/S018-2026-07-27-prefill-continuation.md)

### **S017 · 2026-07-27 · LM Studio assistant role mapping** — every narrator reply was sent as a **user** message. The mapper probed for `add_assistant_message` (which doesn't exist) and silently fell back to `add_user_message`. The real method is `add_assistant_response`. Sending the correct role immediately exposed a latent incompatibility — `lms.Chat` rejects consecutive assistant responses — so the mapper now collapses narrator-message runs into one turn, joining direct after a `length` stop and with a paragraph break otherwise. Verified against the live model. Blocks S018. → [archive](archive/S017-2026-07-27-lmstudio-assistant-role-mapping.md)

### **S009 · 2026-07-27 · Admin panel — session/conversation debugging (MVP)** — backend JSON API (users list, sessions, transcript, traces, delete session, block/unblock user) + Vue SPA frontend (mobile-first, Pinia + vue-router). No auth (Tailscale trust). End-to-end live-verified against real Postgres on 2026-07-24 (data flow only; browser eyeball deferred). Static-file serving from FastAPI is still dev-server-only. Produced S010 + S011 follow-ups. → [archive](archive/S009-2026-07-27-admin-panel-session-debugging.md)

### **S014 · 2026-07-27 · Session directives — Director Mode, Scenario Rules, Language** — `/director` (one turn, cleared by the generation that consumes it), `/rule add|remove`/`/rules` (persistent, never-reused ids), `/language` (persistent). New `SessionDirectives` value object on `ScenarioSession` in a dedicated `scenario_sessions.directives` JSONB column (migration 0008, verified reversible against the real dev DB with 13 live sessions). Prompt gains Language → Scenario Rules → Director Instructions, omitted when empty. Admin panel shows all three read-only. Live-verified over Telegram. Produced **ADR-025** (reset tiers) and surfaced three provider bugs now boarded as S017/S018/S019. → [archive](archive/S014-2026-07-27-session-directives.md)

### **S013 · 2026-07-26 · Retire JSON persistence backend** — Postgres is now the sole runtime backend (ADR-024): all 6 JSON stores deleted, `PlaythroughService` reads scenarios from `ScenarioDefinitionStore` directly, the JSON catalog loader recycled into `ScenarioTransferService` (import/export), tests get a testcontainers-backed Postgres fixture (`uv run pytest` needs zero manual setup). 254 passed, mypy + ruff clean. Live-verified against a real dev Postgres. → [archive](archive/S013-2026-07-26-retire-json-persistence.md)

### **S010 · 2026-07-26 · Admin panel — scenario catalog management** — landed together with S013 (which it depended on). Scenario CRUD (`GET/POST/PUT /admin/scenarios`, `POST /admin/scenarios/import`) + session export/import, all sharing one validation path via `ScenarioTransferService`. Frontend: scenario list/detail/edit pages (raw-JSON-textarea editor, the epic's own MVP bar) + a session-export button on S009's session detail page. Live-verified: panel-created/edited scenarios are immediately playable through `PlaythroughService`. → [archive](archive/S010-2026-07-26-admin-scenario-catalog-mgmt.md)

### **S007 · 2026-07-23 · DB startup health probe + `/health`** — `PostgresHealthProbe` (`ping` + schema-version drift warning) wired into lifespan via a protocol (no SQLAlchemy leak); fails fast by default on unreachable DB (`RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST`); `/health` gained `db`. Live-verified: real boot shows `available`; a forced one-step downgrade fired the drift warning without blocking startup. 221 passed / 12 skipped, mypy + ruff clean. → [archive](archive/S007-2026-07-23-db-startup-health-probe.md)


### **S006 · 2026-07-23 · Migration-vs-model integrity tests** — Upgrade/downgrade round-trip, autogenerate drift guard, migrate-then-contract fixture running all 7 store contracts against a real-migration schema; single-head check. **Caught a real bug**: `GenerationTraceRecord.session_id` had `index=True` with no matching migration index — fixed. Live PG 12/12 passed. → [archive](archive/S006-2026-07-23-migration-integrity-tests.md)


### **S005 · 2026-07-23 · Conversation store contract (both backends)** — Shared `conversation_store_contract.py` run against JSON (unit) + PG (gated integration, live-verified); PG-only tests for created_at tie-break + `session_id` population. Found metadata "non-str key" filtering is unreachable dead code (JSON-object semantics coerce keys to str first). → [archive](archive/S005-2026-07-23-conversation-store-contract.md)


### **S004 · 2026-07-23 · PG parity for identity + trace stores** — `PostgresUserIdentityStore`/`PostgresGroupIdentityStore`/`PostgresGenerationTraceStore` + migration 0007; wired into `build_container`'s postgres branch; shared `identity_serialization.py`; contract tests (JSON + gated PG). Live-verified: caught + fixed a flush-order FK bug. → [archive](archive/S004-2026-07-23-pg-identity-trace-stores.md)


<!-- Trimmed 2026-07-23: S001-S003 and the unlabeled 2026-07-22 access-control card are still
     in archive/ with full detail; removed here to keep this column glanceable. -->

### **S008** · Remove legacy WorldStore + DB docs refresh — delete the unwired character-era `WorldStore` port/impl/test + orphaned `default_world_id`; rewrite character-centric `DATABASE_MODEL.md`. **Note (2026-07-23): mis-filed here — checklist is still all unchecked and the code is still present; not actually done.** → [epic](epics/S008-remove-worldstore-docs.md)


