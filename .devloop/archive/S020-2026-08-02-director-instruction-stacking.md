> 🗄️ **ARCHIVED — COMPLETED 2026-08-02.** Frozen; do not edit. Kept as evolution history.
> **Result:** `/director` notes now **stack** instead of silently overwriting.
> `SessionDirectives.director_instruction: str` became `director_instructions: tuple[str, ...]`;
> each command appends, all queued notes render as a list in the `[Director Instructions]`
> prompt block, and the consuming generation clears the whole queue as a unit. The Telegram
> confirmation reports the queued count ("Director note added — 2 queued"), and a bare
> `/director` lists every pending note instead of offering to replace one. The stored JSONB
> shape changed with it, so **migration `20260802_0011` converts the data** — read-side compat
> was rejected in favour of moving the rows, since a row left in the old shape reads back as an
> empty queue and the player's armed note would vanish on the next load.

# S020 · Let `/director` stack instead of silently overwriting

**Status:** ✅ COMPLETE (2026-08-02)
**Effort:** ~half a day (as estimated)
**Risk:** Low — one field's shape (domain object, serializer, builder, adapter, admin panel)
plus a JSONB data migration; no DDL.

## Problem

`SessionDirectives.director_instruction` was a single `str`. Each `/director <instruction>`
**replaced** it via `replace(self, director_instruction=cleaned)`. Sending several `/director`
commands before the next reply consumed only the last one — the earlier notes were silently
dropped, no warning. The adapter half-acknowledged this: a bare `/director` said "A director
note is already queued… Send /director <instruction> to replace it", but `/director <text>`
with an argument overwrote silently and confirmed with a flat "Director note set."

## What was built

- **Domain** (`core/scenario/session_directives.py`): `director_instructions: tuple[str, ...]`.
  `with_director_instruction` appends; `without_director_instructions` clears the queue; new
  `has_director_instructions` predicate reads at the call sites that used truthiness on a string.
- **Prompt** (`core/conversation/builder.py`): the `[Director Instructions]` section renders
  every queued note as a bullet list in sent order, and its wording moved to the plural
  ("Follow them silently…"). Sent order matters — a later note reads as refining an earlier one.
- **Services**: `SessionDirectiveService.set_director_instruction` → `add_director_instruction`
  (it appends now; the old name lied), `clear_director_instruction` →
  `clear_director_instructions`. `ChatService._consume_director_instruction` clears the queue as
  a unit after a *successful* generation, unchanged in lifecycle.
- **Telegram** (`adapters/telegram/adapter.py`): the confirmation reports the queued count so a
  player can see earlier notes are still armed; a bare `/director` lists all pending notes; the
  "will replace it" wording is gone, and the usage text says notes can be queued.
- **Admin panel**: `director_instructions: list[str]` on the API model, rendered as a numbered
  read-only list in `SessionDetailPage.vue`, zod schema updated.
- **Migration `20260802_0011`**: rewrites the `scenario_sessions.directives` JSONB —
  `{"director_instruction": "x"}` → `{"director_instructions": ["x"]}`, empty string → `[]`,
  old key dropped. Reversible: `downgrade` collapses back to the single string, keeping the
  first note (at most one note can exist in data written before the upgrade, so it is exact for
  every real row). Idempotent — keyed on `WHERE directives ? 'director_instruction'`.

### Decision: migrate the data, don't tolerate the old shape

The epic left this open (read-side compat vs. requiring `/clear`). Pablo called it: **migrate**.
A stored row in the old shape is not merely stale — it deserializes to an *empty* queue, so the
player's armed note disappears with no error, which is the same "the code was fixed and the data
was not" failure that cost S016 a second pass. The serializer still accepts the legacy key on
read, deliberately scoped to **session export files** (a transfer format outlives the schema it
was dumped from); the database is converted, not tolerated.

## Tasks

- [x] `session_directives.py` — tuple field, append, clear-as-a-unit, `has_director_instructions`.
- [x] `builder.py` — render every queued note in `[Director Instructions]`.
- [x] `scenario_serialization.py` — list payload; legacy single-string key accepted on read for
      export files only.
- [x] `adapter.py` `_handle_director` — append, count in the confirmation, list on bare
      `/director`, no more "replace" wording.
- [x] Admin panel — `AdminSessionDirectivesResponse.director_instructions`, list rendering.
- [x] **Alembic migration converting existing rows** (added to the epic's scope on 2026-08-02).
- [x] Docs — `DOMAIN_MODEL.md`, `DATABASE_MODEL.md`, `ARCHITECTURE.md`.

## Verification

- [x] Unit: append 3 notes → all 3 in the built prompt, in order; a successful generation clears
      all 3 at once; queue round-trips through the serializer at 0/1/N notes; pre-S020 payloads
      load as a one- or zero-element queue.
- [x] Telegram: confirmation reports the count, bare `/director` lists every queued note.
- [x] **Migration, against a real Postgres** (`test_pre_s020_director_notes_are_converted_to_a_queue`):
      seeds pre-S020 rows at revision `20260727_0010`, upgrades to head, asserts the array shape
      and that the old key is *gone* (not shadowed), then downgrades and asserts the string is
      back. Sits alongside the existing upgrade/downgrade round-trip in
      `test_migration_integrity_postgres.py`.
- [x] `uv run pytest` 450 passed · `uv run mypy .` at baseline (`src/` clean) · `uv run ruff
      check .` clean · frontend `npm run typecheck` + `build` clean.
- [ ] **Live over Telegram** — not run. Requires applying `alembic upgrade head` to the dev
      Postgres and stacking two notes on a real session.
