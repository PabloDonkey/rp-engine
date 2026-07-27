# S016 · Session lifecycle timestamps + soft delete (fixes session resurrection)

**Status:** 🔵 Backlog
**Effort:** ~1 day
**Risk:** Low-Medium (schema + one query-semantics change that every session lookup inherits;
the risk is *missing* a call site, not the change itself)
**Relates to:** **ADR-025** (session reset tiers) — this fixes that ADR's third negative
consequence. **Blocks/pairs with [S015](S015-user-persona-capture.md)**, which adds `/clear`,
a third path that supersedes a session.

## Problem

`/restart` (and `/clear`, once S015 lands) creates a **new** `ScenarioSession` and leaves the
old row in place. Nothing marks the old one as finished, and
`ScenarioSessionStore.find_by_definition` selects with **no `ORDER BY`**:

```python
# infrastructure/postgres/repositories/scenario_session_store.py
statement = select(ScenarioSessionRecord).where(
    ScenarioSessionRecord.owner_kind == owner_kind,
    ScenarioSessionRecord.owner_id == owner_id,
    ScenarioSessionRecord.scenario_definition_id == scenario_definition_id,
)
... await db_session.scalar(statement)   # arbitrary row among N matches
```

`PlaythroughService.start` uses that lookup to decide "resume the existing session for this
scenario". So after a restart, `/play <same-id>` can **resurrect a pre-restart session and its
old transcript** — non-deterministically, which is the worst way for it to fail. To the player
it looks like the restart silently didn't take.

Deleting the superseded row would fix it, but throws away exactly the data that is most useful
for debugging a bad playthrough or analysing how sessions actually get used.

## Decision

Give `ScenarioSession` a lifecycle and soft-delete superseded sessions instead of orphaning or
purging them.

| Field | Meaning |
|---|---|
| `created_at` (exists) | when the session was created |
| `updated_at` (new) | last write of any kind |
| `deleted_at` (new, nullable) | **null = live session**; set = superseded by a `/restart` or `/clear` |

`deleted_at IS NULL` becomes the definition of "the current session", and the resurrection bug
disappears because `find_by_definition` stops seeing superseded rows at all. Soft-deleted
sessions stay fully readable by id, so the admin panel can open their transcripts and traces.

**Hard delete stays hard.** The admin panel's explicit "Delete session" (`AdminService.delete_session`
→ `store.delete`) remains a real purge. Soft delete is what *the engine* does on reset; hard
delete is what *an operator* does on purpose. Two different intents, two different operations.

## Design notes / decisions to make at implementation time

- **Naming.** `deleted_at` is what was asked for and matches the conventional soft-delete idiom.
  `superseded_at` would describe the actual event more precisely (nobody deleted anything — a
  reset replaced it). Pick one and use it everywhere; not worth a long debate, but worth five
  seconds before the migration is written, because renaming a column later costs a migration.
- **Who stamps `updated_at`.** Three options, one of which is a trap:
  - *(a) Repository-managed* — `save()` sets `updated_at` in the upsert (`insert().values(...)`
    and the `on_conflict_do_update` `set_`). Simplest, impossible to forget. Costs: `save()`
    currently returns the *input* session, and the contract test asserts `returned == session`
    — it would have to return the re-read row (or the domain object with the new stamp).
  - *(b) Domain-managed* — a `ScenarioSession.touch()` returning a copy with a new
    `updated_at`, called by mutating use cases. Explicit and testable with a fixed clock, but
    easy to forget at a new call site.
  - *(c) `onupdate=func.now()` on the column — **does not work here.** SQLAlchemy's `onupdate`
    fires for ORM/Core `UPDATE` statements; this store writes via
    `insert().on_conflict_do_update()`, which bypasses it. Anyone reaching for the obvious
    option will get a silently-stale column.

  Recommendation: **(a)**, and update the contract test.
- **`created_at` is currently overwritten on upsert.** The `on_conflict_do_update` `set_` clause
  includes `created_at: excluded.created_at`, so re-saving a session rewrites its creation
  timestamp from whatever the in-memory object carries. Harmless today (the domain object
  round-trips the original), but with `created_at` becoming a lifecycle field it should be
  insert-only — drop it from the `set_` clause while in here.
- **Index.** The composite `ix_scenario_sessions_owner_definition` backs `find_by_definition`.
  Either add `deleted_at` to it or make it a partial index (`WHERE deleted_at IS NULL`). Partial
  is the better fit — every hot lookup filters on live sessions only.

## Tasks

### Domain
- [ ] Add `updated_at: datetime` and `deleted_at: datetime | None` to `ScenarioSession`
      (frozen dataclass; `deleted_at` defaults to `None`).
- [ ] A narrow transition for supersession (e.g. `mark_deleted(at=...)`) rather than a general
      setter — mirrors how `with_directives(...)` was added in S014.

### Persistence
- [ ] Alembic migration, reversible, chained after the current head (`20260726_0008` at time of
      writing — recheck): add `updated_at timestamptz NOT NULL` (backfill existing rows from
      `created_at`, not `now()`, so history isn't falsified) and `deleted_at timestamptz NULL`.
      Rework `ix_scenario_sessions_owner_definition` as a partial index.
- [ ] `ScenarioSessionRecord`, the repository's `save()`/`_to_domain()`, and the shared
      `scenario_session_to_payload`/`from_payload` (transfer format, ADR-024) carry both fields.
- [ ] Verify `upgrade head` **and** `downgrade` against a real DB (CLAUDE.md bar).

### Store semantics — the actual fix
- [ ] `find_by_definition`: filter `deleted_at IS NULL`, and add `ORDER BY created_at DESC` as a
      belt-and-braces tiebreak so a duplicate-live-row bug can never again be non-deterministic.
- [ ] `get_active_for_owner`: filter `deleted_at IS NULL` defensively (the active pointer is
      already repointed on reset, so this is a second line of defence, not the mechanism).
- [ ] `get_by_id`: **no filter** — soft-deleted sessions must stay openable by id, that's the
      whole point.
- [ ] `find_by_owner`: gains `include_deleted: bool = False`. Default-off keeps every engine
      caller honest; the admin panel opts in.
- [ ] Extend the store contract suite: a soft-deleted session is invisible to
      `find_by_definition`/`get_active_for_owner`, still readable via `get_by_id`, and appears in
      `find_by_owner` only with `include_deleted=True`.

### PlaythroughService
- [ ] `restart` (and S015's `clear`) stamp `deleted_at` on the outgoing session before `_begin`
      creates its replacement.
- [ ] Regression test that reproduces the original bug: start → restart → `/play <same-id>`
      returns the **post**-restart session, deterministically, with its own transcript.

### Admin panel — the payoff
- [ ] `AdminService.list_user_sessions` passes `include_deleted=True`; `AdminSessionResponse`
      exposes `created_at`, `updated_at`, `deleted_at`.
- [ ] Session list: superseded sessions render with a muted "superseded" badge and their
      `deleted_at`, sorted newest-first, so a playthrough's full history is visible in one place.
- [ ] Decide what `session_count` on the users list means — live-only, or `3 live / 7 total`.
      Live-only is the less surprising default; total is the more useful number for analysis.
      (`AdminService.list_users` currently counts whatever `find_by_owner` returns, so this
      changes implicitly if the flag is passed there too — make it a deliberate choice.)

## Verification
- [ ] Unit + contract tests as above; the resurrection regression test is the one that matters.
- [ ] Migration round-trip against a real DB, with existing rows keeping their true `created_at`
      as `updated_at` rather than being stamped `now()`.
- [ ] Live-verify: start a scenario, play a few turns, `/restart`, play again, then `/play <same
      id>` — the post-restart story is the one that resumes. Both sessions are visible in the
      admin panel, the older one flagged superseded with its transcript intact.

## Out of scope
Retention/purge policy for soft-deleted sessions (they accumulate forever under this epic).
If that becomes a real concern rather than a hypothetical one, it's a follow-up — and probably
an ADR, since "how long do we keep player conversation data" is a decision, not an implementation
detail.
