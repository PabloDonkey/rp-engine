# RP Engine — Dev Board

## 🔵 Backlog

### **S010** · Admin panel — scenario catalog management — list/view/create/edit `ScenarioDefinition`s from the panel instead of hand-editing JSON. Open Q: edit JSON files vs. DB-backed store. Follows S009. → [epic](epics/S010-admin-scenario-catalog-mgmt.md)

### **S011** · Admin panel — ops dashboard — landing overview: active sessions, DB health (reuses S007 `/health`), recent LLM latency/errors. Read-only. Follows S009. → [epic](epics/S011-admin-ops-dashboard.md)

### Activate StoryGraph / scenario branching — `StoryGraph`+`StoryBeat` exist as inert data; nothing drives beats yet. _(bare card — gets an S### when promoted to an epic)_ → see `../docs/DOMAIN_MODEL.md`


## 🟡 Up Next

_(nothing queued — see Backlog)_

## 🟢 In Progress

### **S012** · Admin panel — thinking trace + per-message debug menu — captures model "thinking"/reasoning content (was discarded by the LM Studio provider), stamps turn number onto each stored message, and replaces the transcript's global "Show generation traces" toggle with a per-message filter row (Thinking / Raw trace / System prompt / Turn metadata checkboxes, independent per message). Backend + frontend built, pytest/mypy/ruff/typecheck/build all clean, end-to-end data flow verified against a real (temp-dir) JSON backend with only the raw LLM call stubbed (2026-07-24). Remaining: exercise a real thinking-capable LM Studio model, browser eyeball. Follows S009. → [epic](epics/S012-transcript-thinking-and-per-message-debug-menu.md)

### **S009** · Admin panel — session/conversation debugging (MVP) — Vue SPA + JSON admin API on FastAPI, backend + core flow built and live-verified against real Postgres data (2026-07-24). Users → sessions → transcript + generation traces; delete session; block/unblock user. No auth (Tailscale trust). Remaining: browser/phone eyeball check, static-serve wiring, tests, ADR — see epic. → [epic](epics/S009-admin-panel-session-debugging.md)

## ✅ Done (recent)

### **S007 · 2026-07-23 · DB startup health probe + `/health`** — `PostgresHealthProbe` (`ping` + schema-version drift warning) wired into lifespan via a protocol (no SQLAlchemy leak); fails fast by default on unreachable DB (`RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST`); `/health` gained `db`. Live-verified: real boot shows `available`; a forced one-step downgrade fired the drift warning without blocking startup. 221 passed / 12 skipped, mypy + ruff clean. → [archive](archive/S007-2026-07-23-db-startup-health-probe.md)


### **S006 · 2026-07-23 · Migration-vs-model integrity tests** — Upgrade/downgrade round-trip, autogenerate drift guard, migrate-then-contract fixture running all 7 store contracts against a real-migration schema; single-head check. **Caught a real bug**: `GenerationTraceRecord.session_id` had `index=True` with no matching migration index — fixed. Live PG 12/12 passed. → [archive](archive/S006-2026-07-23-migration-integrity-tests.md)


### **S005 · 2026-07-23 · Conversation store contract (both backends)** — Shared `conversation_store_contract.py` run against JSON (unit) + PG (gated integration, live-verified); PG-only tests for created_at tie-break + `session_id` population. Found metadata "non-str key" filtering is unreachable dead code (JSON-object semantics coerce keys to str first). → [archive](archive/S005-2026-07-23-conversation-store-contract.md)


### **S004 · 2026-07-23 · PG parity for identity + trace stores** — `PostgresUserIdentityStore`/`PostgresGroupIdentityStore`/`PostgresGenerationTraceStore` + migration 0007; wired into `build_container`'s postgres branch; shared `identity_serialization.py`; contract tests (JSON + gated PG). Live-verified: caught + fixed a flush-order FK bug. → [archive](archive/S004-2026-07-23-pg-identity-trace-stores.md)


<!-- Trimmed 2026-07-23: S001-S003 and the unlabeled 2026-07-22 access-control card are still
     in archive/ with full detail; removed here to keep this column glanceable. -->

### **S008** · Remove legacy WorldStore + DB docs refresh — delete the unwired character-era `WorldStore` port/impl/test + orphaned `default_world_id`; rewrite character-centric `DATABASE_MODEL.md`. **Note (2026-07-23): mis-filed here — checklist is still all unchecked and the code is still present; not actually done.** → [epic](epics/S008-remove-worldstore-docs.md)


