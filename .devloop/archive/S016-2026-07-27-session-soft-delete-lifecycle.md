> 🗄️ **ARCHIVED — COMPLETED 2026-07-27.** Frozen; do not edit. Kept as evolution history.
> **Result:** Session resurrection is closed. `ScenarioSession` gained `updated_at`
> (repository-stamped on every `save`) and `deleted_at`; `deleted_at IS NULL` **is** "the
> current session", the composite index became partial, and `find_by_definition` filters and
> orders deterministically. `/restart` and `/clear` stamp the outgoing session instead of
> orphaning it, so it keeps its whole transcript and stays readable by id — which is why
> `/restart` deliberately no longer wipes the old conversation.
> **It took two passes.** The first (migration `20260727_0009`) fixed the code and left the
> data broken: `deleted_at` was NULL on every existing row, so every session orphaned by a
> pre-S016 restart still counted as live and `/play <id>` still resurrected old stories. Live
> testing caught it; the unit regression test could not, because it ran against a fake store
> written to filter correctly. Migration `20260727_0010` backfills — one live session per
> owner+scenario, survivor chosen by active pointer → last message → `created_at`, stamped with
> its own last sign of life rather than `now()` — and makes the partial index **unique** so it
> cannot recur. On the dev DB: 13 live → 10 live, zero duplicates remaining.
> `ScenarioTransferService.import_session` is the one caller that can hit the constraint in
> normal use; the admin route maps it to a 409.
> **The test that should have existed first:**
> `tests/integration/infrastructure/test_playthrough_reset_postgres.py`, driving
> `PlaythroughService` against the real repositories. A fake store can only test the caller,
> never the invariant.
> **Live-verified over Telegram 2026-07-27.** The admin-panel presentation of superseded
> sessions was deliberately left out of scope — see the Backlog card.

# S016 · Session lifecycle timestamps + soft delete (fixes session resurrection)

**Status:** ✅ COMPLETE — archived 2026-07-27. Landed with [S015](S015-2026-07-27-user-persona-capture.md), then
**fixed again the same day** — the first pass fixed the *code* and left the *data* broken
(see "The miss" below). Resurrection is now closed at both levels and enforced by a unique
index. The admin-panel presentation (the "payoff" section below) was cut from scope and lives on as a Backlog card.
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

- **Naming — decided: `deleted_at`.** (What was asked for, and the conventional idiom.)
  `deleted_at` is what was asked for and matches the conventional soft-delete idiom.
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
- [x] Add `updated_at: datetime` and `deleted_at: datetime | None` to `ScenarioSession`
      (frozen dataclass; `deleted_at` defaults to `None`).
- [x] A narrow transition for supersession (e.g. `mark_deleted(at=...)`) rather than a general
      setter — mirrors how `with_directives(...)` was added in S014.

### Persistence
- [x] Alembic migration, reversible, chained after the current head (`20260726_0008` at time of
      writing — recheck): add `updated_at timestamptz NOT NULL` (backfill existing rows from
      `created_at`, not `now()`, so history isn't falsified) and `deleted_at timestamptz NULL`.
      Rework `ix_scenario_sessions_owner_definition` as a partial index.
- [x] `ScenarioSessionRecord`, the repository's `save()`/`_to_domain()`, and the shared
      `scenario_session_to_payload`/`from_payload` (transfer format, ADR-024) carry both fields.
- [x] Verify `upgrade head` **and** `downgrade` against a real DB (CLAUDE.md bar).

### Store semantics — the actual fix
- [x] `find_by_definition`: filter `deleted_at IS NULL`, and add `ORDER BY created_at DESC` as a
      belt-and-braces tiebreak so a duplicate-live-row bug can never again be non-deterministic.
- [x] `get_active_for_owner`: filter `deleted_at IS NULL` defensively (the active pointer is
      already repointed on reset, so this is a second line of defence, not the mechanism).
- [x] `get_by_id`: **no filter** — soft-deleted sessions must stay openable by id, that's the
      whole point.
- [x] `find_by_owner`: gains `include_deleted: bool = False`. Default-off keeps every engine
      caller honest; the admin panel opts in.
- [x] Extend the store contract suite: a soft-deleted session is invisible to
      `find_by_definition`/`get_active_for_owner`, still readable via `get_by_id`, and appears in
      `find_by_owner` only with `include_deleted=True`.

### PlaythroughService
- [x] `restart` (and S015's `clear`) stamp `deleted_at` on the outgoing session before `_begin`
      creates its replacement.
- [x] Regression test that reproduces the original bug: start → restart → `/play <same-id>`
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


## What landed on 2026-07-27 (with S015)

Migration `20260727_0009` (shared with S015's persona columns), verified reversible against
the real dev Postgres with 13 live sessions — `updated_at` backfilled from each row's own
`created_at`, `ix_scenario_sessions_owner_definition` reworked as
`WHERE deleted_at IS NULL`, `created_at` dropped from the upsert's `SET` clause.

Store semantics as specified: `find_by_definition` filters `deleted_at IS NULL` and orders
`created_at DESC`; `get_active_for_owner` filters defensively; `get_by_id` is unfiltered;
`find_by_owner` gained `include_deleted: bool = False`. `updated_at` is repository-managed
(option **(a)**), so `save()` returns the stamped session — the contract test asserts this.
`restart` and `clear` share `PlaythroughService._reset` and stamp the outgoing session.
The resurrection regression test is
`test_replaying_a_scenario_after_a_restart_resumes_the_new_session`.

One behavior change worth flagging: **`/restart` no longer clears the outgoing session's
transcript.** Keeping it is the point of superseding rather than purging, and it is what
makes the admin-panel work below worth doing.

### Still open (the admin-panel payoff)

The backend is already prepared: `AdminService.list_user_sessions` passes
`include_deleted=True`, and `AdminSessionResponse` exposes `created_at`, `updated_at`,
`deleted_at`, and the persona. What is missing is the **frontend**: a muted "superseded"
badge, newest-first sorting, and the deliberate decision about what `session_count` on the
users list should mean (it is currently live-only, which was the recommended default).


## The miss, and the second fix (same day)

**Reported after live testing: "soft delete doesn't work, old story comes back to life."**
It was a real hole, and the tests did not catch it for a specific, repeatable reason.

**What was wrong.** Migration `0009` added `deleted_at` and left it NULL on every existing
row. Correct as a column default — wrong as data: *every session orphaned by a `/restart`
from before this epic was therefore still "live"*. The dev DB had six live rows for
`little-pablo-den` across three owners. `find_by_definition` filters `deleted_at IS NULL`,
so it still had several candidates and still picked among them; `/play <id>` still resumed
a pre-restart story. **The code was fixed and the bug survived in the rows.**

**Why the tests passed anyway.** The regression test I wrote ran against
`FakeScenarioSessionStore` — a fake *I* had just written to filter superseded sessions
correctly. It proved the service asked for the right thing, never that the data could
answer it. And no test started from a database that already contained pre-migration
orphans, which is the only state where the bug lives.

**The fix — migration `20260727_0010`:**

1. **Backfill.** One live session per (owner_kind, owner_id, scenario_definition_id); the
   survivor is chosen by the owner's active-session pointer, then the most recent
   conversation message, then `created_at`. The rest are stamped with their own last sign of
   life, not `now()`. On the dev DB: 13 live → 10 live, and the three survivors for
   `little-pablo-den` were exactly the three active-pointer sessions.
2. **A unique partial index**, so it cannot recur. `PlaythroughService` cannot legitimately
   create a second live row, so the constraint costs nothing and turns a silent
   non-deterministic wrong answer into a loud failure.
   `ScenarioTransferService.import_session` is the one caller that can hit it in normal use;
   the admin route maps that to a 409 instead of a 500.

**And the test that should have existed:**
`tests/integration/infrastructure/test_playthrough_reset_postgres.py` drives
`PlaythroughService` against the **real repositories** — start → restart → `/play` the same
scenario, the pre-restart transcript never returning, `/clear` behaving the same way,
duplicate live rows being rejected, and repeated restarts leaving exactly one live session.
The lesson worth keeping: a fake store can only test the caller, never the invariant.
