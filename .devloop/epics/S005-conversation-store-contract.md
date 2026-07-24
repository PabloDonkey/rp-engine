# S005 · Conversation store contract (both backends)

**Status:** 🔵 Backlog
**Effort:** ~2 h
**Risk:** Low-Medium (may surface real PG conversation-store bugs)

## Context

CLAUDE.md states the parity principle: **one contract-test suite run against both backends.**
That holds for `ScenarioDefinitionStore` and `ScenarioSessionStore`, but **not** for
`ConversationStore`:

- `tests/unit/infrastructure/test_json_conversation_store.py` exercises **only** the JSON impl.
- `PostgresConversationStore` (`postgres/repositories/conversation_store.py`) is **never**
  hit by a test — its ordering (`created_at`, then `id`), metadata str/str filtering, `clear()`,
  and `_extract_session_id` parsing are all unverified against a real DB.

## Tasks

- [ ] Extract a shared `tests/unit/infrastructure/contracts/conversation_store_contract.py`
      (`assert_conversation_store_contract`) covering:
  - [ ] save → load round-trip preserving order across many messages
  - [ ] deterministic ordering when `created_at` collides (tie-break on `id`)
  - [ ] metadata preserved; non-str keys/values dropped (matches PG filter)
  - [ ] `clear(memory_key)` isolates by key (doesn't wipe siblings)
  - [ ] `session_`-prefixed memory keys populate `session_id`; others leave it NULL
- [ ] JSON runner (unit) + gated PG runner (integration), refactoring existing JSON test in.

## Verification

- [ ] `uv run pytest` green; `scripts/test_postgres.sh` green.
- [ ] mypy + ruff clean.
