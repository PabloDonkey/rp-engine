# RP Engine — Dev Board

## 🔵 Backlog

### **S020** · `/director` notes silently overwrite instead of stacking — `SessionDirectives.director_instruction` is a single `str`; each `/director <instruction>` replaces it, so sending several before the next reply loses all but the last with no warning. Turn it into a tuple of notes: append per command, render all in the `[Director Instructions]` prompt block, clear as a unit on consume. Touches the domain object, builder, `scenario_serialization.py` (JSONB shape, no migration needed), the adapter's confirmation message, and the admin panel's read-only view. → [epic](epics/S020-director-instruction-stacking.md)

### **S019** · Use the SDK's `LlmReasoningParsing` instead of regexing an internal marker — the provider splits thinking from prose on `__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_<hex>__`, an internal synthetic marker with no compatibility promise. If it ever changes shape the regex stops matching and **the model's entire reasoning gets delivered to the player as the story**. The SDK exposes `reasoning_parsing` (`enabled`/`start_string`/`end_string`) on `LlmPredictionConfig` — declare the delimiters instead of reverse-engineering them, and fail loudly rather than passing an unsplit blob through as prose. Also gives S018 the exact markers if it needs to emit a closed think block. → [epic](epics/S019-lmstudio-reasoning-parsing.md)

### **S015** · User persona capture on new session start (+ `/clear`) — `/play` on a **new** user session (groups skipped, for now) prompts "provide a name + description/likes/dislikes for your character, or /skip" before showing the story intro; first line = name, rest = description; immutable once set; `{{user}}` resolves to the persona name (falls back to Telegram username on `/skip`). Needs a new pending-reply mechanism in the Telegram adapter (none exists today) + an immutable persisted field + migration. **Now also owns `/clear`** per **ADR-025**: `/restart` preserves player-owned settings (persona, language, rules), `/clear` resets them — which is what makes "immutable once set" survivable, so it isn't a follow-up. Also fixes the pre-existing orphaned-session hazard (`find_by_definition` has no `ORDER BY`). Design decisions locked, ready to implement. → [epic](epics/S015-user-persona-capture.md)

### **S016** · Session lifecycle timestamps + soft delete — fixes **session resurrection**: `/restart` leaves the old session row behind and `find_by_definition` has no `ORDER BY`, so `/play <same-id>` can non-deterministically resume a *pre-restart* session and its old transcript. Adds `updated_at` + nullable `deleted_at` to `ScenarioSession` — `deleted_at IS NULL` **is** "the current session"; set = superseded by `/restart` or `/clear`. Superseded sessions stay fully readable by id, so the admin panel can show a playthrough's whole history for debugging/analysis. Admin's explicit "Delete session" stays a real purge. Pairs with S015 (`/clear` adds a third supersede path); addresses ADR-025's third negative consequence. → [epic](epics/S016-session-soft-delete-lifecycle.md)

### **S011** · Admin panel — ops dashboard — landing overview: active sessions, DB health (reuses S007 `/health`), recent LLM latency/errors. Read-only. Follows S009. → [epic](epics/S011-admin-ops-dashboard.md)

### Activate StoryGraph / scenario branching — `StoryGraph`+`StoryBeat` exist as inert data; nothing drives beats yet. _(bare card — gets an S### when promoted to an epic)_ → see `../docs/DOMAIN_MODEL.md`


## 🟡 Up Next

_(nothing queued — see Backlog)_

## 🟢 In Progress

### **S018** · `/continue` by assistant prefill instead of a "please continue" nudge — appending a user directive opens a **new assistant turn**, which is when a reasoning model re-plans from scratch (observed: a resume burned all 2000 tokens thinking and returned no prose). **Probed live 2026-07-27**: a chat ending in `add_assistant_response(partial)` continues the text in place *and emits no reasoning at all*; the user-final control reasoned first; `model.complete()` raw also reasoned. So plain-SDK assistant-final works — no jinja override or REST bypass needed — and it deletes the reasoning pass rather than just re-wording the request. Supersedes the `<notes>` mitigation. Depends on S017. → [epic](epics/S018-prefill-continuation.md) **Code complete 2026-07-27**; 352 passed, mypy + ruff clean; verified end to end against the live model (builder→mapper→provider): prefill continued mid-sentence, in character, **no reasoning pass**, 45 completion tokens, and `finish_reason`/usage now populated. Remaining: the live Telegram read.

### **S017** · LM Studio mapper sends every narrator reply as a **user** message — `_add_assistant_message` probes for `add_assistant_message`, which does not exist on `lms.Chat` (the real method is `add_assistant_response`), so the `getattr` fallback chain silently routes every character reply through `add_user_message`. The model has never seen its own prior output as its own — from its side the player wrote both halves of the roleplay. One-line fix; the value is re-judging output quality afterwards. Blocks S018. Found while probing continuation, 2026-07-27. → [epic](epics/S017-lmstudio-assistant-role-mapping.md) **Code complete 2026-07-27**; 352 passed, mypy + ruff clean; verified end to end against the live model (builder→mapper→provider): prefill continued mid-sentence, in character, **no reasoning pass**, 45 completion tokens, and `finish_reason`/usage now populated. Remaining: the live Telegram read.

### **S012** · Admin panel — thinking trace + per-message debug menu — captures model "thinking"/reasoning content (was discarded by the LM Studio provider), stamps turn number onto each stored message, and replaces the transcript's global "Show generation traces" toggle with a per-message filter row (Thinking / Raw trace / System prompt / Turn metadata checkboxes, independent per message). Backend + frontend built, pytest/mypy/ruff/typecheck/build all clean, end-to-end data flow verified against a real (temp-dir) JSON backend with only the raw LLM call stubbed (2026-07-24). Remaining: exercise a real thinking-capable LM Studio model, browser eyeball. Follows S009. → [epic](epics/S012-transcript-thinking-and-per-message-debug-menu.md)

### **S009** · Admin panel — session/conversation debugging (MVP) — Vue SPA + JSON admin API on FastAPI, backend + core flow built and live-verified against real Postgres data (2026-07-24). Users → sessions → transcript + generation traces; delete session; block/unblock user. No auth (Tailscale trust). Remaining: browser/phone eyeball check, static-serve wiring, tests, ADR — see epic. → [epic](epics/S009-admin-panel-session-debugging.md)

## ✅ Done (recent)

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


