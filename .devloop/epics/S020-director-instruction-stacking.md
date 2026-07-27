# S020 · Let `/director` stack instead of silently overwriting

**Status:** 🔵 Backlog
**Effort:** ~half a day
**Risk:** Low — touches one field's shape (domain object, serializer, builder, admin panel),
no persistence backend change (`directives` is already a JSONB blob, migration-free).

## Problem

`SessionDirectives.director_instruction` is a single `str`. Each `/director <instruction>`
**replaces** it via `replace(self, director_instruction=cleaned)`
([session_directives.py:90-94](../../src/rp_engine/core/scenario/session_directives.py#L90-L94)).
Sending several `/director` commands before the next reply consumes only the last one — the
earlier notes are silently dropped, no warning.

The adapter already half-acknowledges this: a bare `/director` (no argument) replies "A
director note is already queued for the next reply… Send /director <instruction> to replace
it." ([adapter.py:560-565](../../src/rp_engine/adapters/telegram/adapter.py#L560-L565)), but
`/director <instruction>` with an argument overwrites silently — confirmation is just
"Director note set."

## Decision

Make it stack: `director_instruction` becomes a tuple of notes, each `/director <instruction>`
appends, all notes render in the `[Director Instructions]` block, and the whole tuple is
cleared as a unit by the generation that consumes it (same one-turn lifecycle as today, just
plural).

## Tasks

- [ ] `core/scenario/session_directives.py`: change `director_instruction: str = ""` to
  `director_instructions: tuple[str, ...] = ()`. `with_director_instruction` appends instead of
  replacing; `without_director_instruction` clears the whole tuple (same clear-on-consume
  semantics as `_consume_director_instruction` in `chat_service.py`).
- [ ] `core/conversation/builder.py` `_director_instruction_text`
  ([builder.py:352-363](../../src/rp_engine/core/conversation/builder.py#L352-L363)): render
  multiple notes in the `[Director Instructions]` section (e.g. one per line/bullet) instead of
  a single interpolated string.
- [ ] `infrastructure/scenario_serialization.py`: update the payload dict shape for the
  `directives` JSONB column (list instead of single string) — no Alembic migration needed since
  it's JSONB, but existing stored sessions have the old shape; decide read-side compat (treat a
  bare string as a one-element list) vs. requiring `/clear`.
- [ ] `adapters/telegram/adapter.py` `_handle_director`
  ([adapter.py:552-572](../../src/rp_engine/adapters/telegram/adapter.py#L552-L572)): drop the
  "already queued, will replace" warning path (no longer true); confirmation should say how many
  notes are now queued.
- [ ] Admin panel (`admin_models.py` / frontend): director instruction is currently shown as a
  single read-only string — render as a list.
- [ ] Contract/unit tests: `session_directives` unit tests, builder tests for multi-note
  rendering, `scenario_serialization` round-trip with 0/1/N notes.

## Verification
- [ ] Unit: append 3 `/director` notes, confirm all 3 appear in the built prompt, confirm a
  successful generation clears all 3 at once.
- [ ] Live: stack two `/director` notes over Telegram, confirm the reply reflects both, confirm
  `/director` (bare) with a queue shows all pending notes.
