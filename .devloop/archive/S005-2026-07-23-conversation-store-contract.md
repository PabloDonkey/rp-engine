> 🗄️ **ARCHIVED — COMPLETED 2026-07-23.** Frozen; do not edit. Kept as evolution history.
> **Result:** Shared `tests/unit/infrastructure/contracts/conversation_store_contract.py`
> (`assert_conversation_store_contract`) run against JSON (unit) and PG (gated integration,
> live-verified). PG-only edge cases (created_at tie-break, `session_id` population) covered by
> dedicated tests in the PG runner since they aren't observable through the `ConversationStore`
> port alone. Found and documented that "non-str metadata key" filtering is dead code reachable
> only via out-of-band data — JSON-object semantics coerce dict keys to strings before either
> backend's filter runs. Full suite 215 passed / 8 skipped, mypy clean on `src/`, ruff clean;
> live PG run 8/8 passed.

---

# S005 · Conversation store contract (both backends)

**Status:** ✅ COMPLETE — archived 2026-07-23
**Effort:** ~2 h
**Risk:** Low-Medium (may surface real PG conversation-store bugs)

## Context

CLAUDE.md states the parity principle: **one contract-test suite run against both backends.**
That held for `ScenarioDefinitionStore` and `ScenarioSessionStore`, but **not** for
`ConversationStore`:

- `tests/unit/infrastructure/test_json_conversation_store.py` exercised **only** the JSON impl.
- `PostgresConversationStore` (`postgres/repositories/conversation_store.py`) was **never**
  hit by a test — its ordering (`created_at`, then `id`), metadata str/str filtering, `clear()`,
  and `_extract_session_id` parsing were all unverified against a real DB.

## Tasks

- [x] Extracted a shared `tests/unit/infrastructure/contracts/conversation_store_contract.py`
      (`assert_conversation_store_contract`) covering:
  - [x] save → load round-trip preserving order across many messages
  - [x] metadata preserved; non-str **value** dropped on load (matches PG filter). Scoped down
        from "non-str keys/values": a non-str dict *key* can never reach either backend's
        filter in the first place — both round-trip metadata through JSON-object semantics
        (Python `json.dumps` / JSONB), which coerce dict keys to strings before the isinstance
        filter runs. Confirmed this by writing the original two-bad-entries test first; the
        JSON-store run showed the "bad key" survived (as `"7"`) rather than being dropped.
  - [x] `clear(memory_key)` isolates by key (doesn't wipe siblings)
  - [x] Deterministic ordering when `created_at` collides (tie-break on `id`) and
        `session_`-prefixed memory keys populating `session_id` (vs. `NULL` for others) are
        **PG-only** tests in the integration runner, not the shared contract — neither is
        observable through the `ConversationStore` port (no timestamp control, no `session_id`
        getter), so they're verified by inserting `ConversationMessageRecord` rows directly and
        querying the table.
- [x] JSON runner (`test_json_conversation_store.py`, refactored to call the shared contract)
      + gated PG runner (`tests/integration/infrastructure/test_conversation_store_contract_postgres.py`,
      new — `assert_conversation_store_contract` plus the two PG-only tests above).

## Verification

- [x] `uv run pytest` green: 215 passed, 8 skipped (PG-gated tests skip without
      `RP_ENGINE_RUN_POSTGRES_TESTS=1`).
- [x] mypy clean on `src/`; ruff clean.
- [x] Manual, against a real Postgres 17 container: full gated PG integration suite —
      8/8 passed (3 conversation-store tests + the 5 from S004).
