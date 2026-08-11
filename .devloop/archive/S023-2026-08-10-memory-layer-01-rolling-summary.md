> 🗄️ **ARCHIVED — COMPLETED 2026-08-10.** Frozen; do not edit. Kept as evolution history.
> **Result:** the engine now keeps a running "story so far". What falls past 75% of the context
> budget is condensed into one recap, the recap is condensed again when it outgrows its own
> share, and it reaches every prompt as a `[Story So Far]` block ranked directly below the
> window. Landed with it: the **background worker** ADR-026 designed in S021 (in-process
> `asyncio.Queue`, one job per session, bounded, cancelled on shutdown), `SessionSummary` +
> `SessionSummaryStore` + the `session_summaries` table (migration `20260810_0012`, reversible
> both ways against a real Postgres), per-source budget shares on `MemorySettings`, the `/memory`
> command, and an admin-panel switch that also shows the stored recap.
> **`LMStudioConversationSummarizer` is wired in for the first time**, with its character-handoff
> prompt replaced by two rolling-recap prompts.
> **One deliberate deviation from ADR-026**, argued in Scope below: `MemoryObserveContext` gained
> two budget fields.
> **Not verified over Telegram** — that check is still open, together with S022's. See
> Verification.

# S023 · Memory layer 01 — rolling summary

**Status:** ✅ COMPLETE — 2026-08-10. Every scope item is built and tested. The open items are
the three live runs, see Verification.
**Depends on:** **S022** (the pipeline, the token counter, the `MemorySource` port) → **done
2026-08-10**, see [archive](S022-2026-08-10-memory-layer-00-window-and-pipeline.md).
**Design source:** [Five ways to remember a story](https://claude.ai/code/artifact/c77560f4-99c2-4566-8b1c-9687d3893ac5)
— Pablo's chosen memory architecture. ADR-026 cites this link.
**Effort:** ~1–2 days
**Risk:** Low-to-medium — no new infrastructure; the risk is summary drift, not breakage.

## Problem

Layer 00 keeps a budgeted window, so everything older than the window was simply gone. The story
so far disappeared with no trace.

## Goal

Every N turns, condense what fell out of the window into a running recap, and re-condense recaps
when they grow too long. Injected on every turn as "the story so far".

## Scope

- [x] **The background worker.** `BackgroundTaskScheduler` port (`core/ports/`), one `submit`
      method returning whether the job was accepted; `AsyncioTaskScheduler`
      (`infrastructure/tasks/`) behind it. Started and cancelled by `app/lifespan.py`, before the
      Telegram runtime on the way up and after it on the way down. Dedupe by key, bounded queue
      (64) that logs and drops on overflow, cancel rather than drain on shutdown, and every job
      wrapped so a failure is logged and swallowed. `ChatService._observe_turn` is the single
      place the write half starts, keyed `memory:<session id>` — one key per session, not per
      layer, because the pipeline runs every enabled layer in one job and two fast turns must
      collapse into one pass.
- [x] `RollingSummarySource` (`core/memory/rolling_summary_source.py`):
      - `recall` → one `[Story So Far]` fragment at priority 80, directly below the window's 100
        and above every later layer. One indexed read; the turn pays nothing else.
      - `observe` → re-reads the transcript and the watermark and decides for itself. The job
        carries the session id and the turn, never message text.
- [x] Queue at a **high-water mark below the budget** (75%, `RP_ENGINE_MEMORY_SUMMARY_HIGH_WATER_SHARE`).
      One walk from newest to oldest marks both the high-water line and the window edge, so the
      fold region and the alarm come from the same pass — and it stops at the window edge, so it
      costs one token count per message the window can hold, not one per message ever stored.
      Those are the counts layer 00 already asked for, so they come from the cache.
- [x] The fold boundary is pulled back to just after a narrator reply. Folding half a turn would
      put the player's line in the recap and leave the answer to it in the window, which reads as
      the story answering something it was never asked.
- [x] Re-condense: when the stored recap exceeds its share of the budget, the recap itself is
      summarized. **One pass, not a loop** — a recap still too long after condensing is reported
      by the pipeline dropping it, which is a fact worth seeing; a loop that calls the model
      until a number comes down is not.
- [x] Persistence: **one new table**, `session_summaries`, and migration `20260810_0012`.
      `covers_through_turn` counts narrator replies, the same clock the stored messages carry in
      their `turn` metadata. `save()` is an upsert that leaves `created_at` alone: the recap is
      one long-lived value that is rewritten, not a version per pass.
- [x] Store contract test (`tests/unit/infrastructure/contracts/session_summary_store_contract.py`),
      run against Postgres in both suites — the shared-container one and the one whose schema
      real Alembic migrations built.
- [x] `LMStudioConversationSummarizer` wired into `app/main.py` for the first time.
- [x] Two rolling-recap prompts replace the character-handoff one, which nothing called: one
      folds new turns into the existing recap, one condenses the recap. Both take a **word**
      target rather than a token budget — a model follows an instruction about words far better,
      and the caller counts the result afterwards either way. The old
      `summarize_recent_conversation` is gone rather than kept beside them: it had no caller, and
      two prompts where one is used is how the wrong one gets picked later.
- [x] Per-source budgets on `MemorySettings`, which S022 cut as YAGNI. A `MemorySourceBudget` is
      a **share**, not a token count, for the reason the whole budget is one (ADR-026): a
      hand-set number goes silently wrong the moment a different model is loaded. Layer 01 takes
      0.25. A layer with no share gets what the enabled shares leave, which is what layer 00
      gets, so the shares need not add up to one. **The subtraction is the point, and it was a
      real defect while it was missing:** offered the whole budget, the window fills it with
      turns on any long story, and the priority cut then drops the recap every single turn — the
      share would have bought layer 01 nothing. The cost is a wasted share when a recap is
      shorter than its allowance. A layer this build does not run reserves nothing, so a session
      carrying a switched-on layer from a newer build cannot shrink an older build's window.
- [x] `/memory` alongside `/rules` and `/director`: bare lists the layers and their state,
      `/memory summary on|off` switches one. It speaks the player's word (`summary`) and accepts
      the engine's (`rolling_summary`).
- [x] Admin panel: `PUT /admin/sessions/{id}/memory` switches one layer,
      `GET /admin/sessions/{id}/summary` returns the stored recap, and the session page shows
      both — including how far the recap reaches, what it cost, and which model wrote it.

### Layer 01 is on by default

`DEFAULT_ENABLED_SOURCES` is `("rolling_summary",)`. A session that has to be told to remember is
a session that already forgot. **One consequence worth knowing:** a session saved between S022
and S023 has an explicit empty `enabled_sources` in its payload, which reads as "the player
switched it off" and stays off. `/memory summary on` fixes it per session. No migration was
written for it, because there is no way to tell those rows from a genuine opt-out, and inventing
one would overwrite a real choice.

### The one deviation from ADR-026

**`MemoryObserveContext` gained `memory_budget` and `source_budget`.** ADR-026 lists three fields
for it: session id, scenario id, turn. But the worker has to know how much room the prompt has,
twice over: where the high-water mark sits, and how long the recap may be. Rule 3 says the
pipeline owns the budget, so the pipeline fills both fields in **when the job runs**, not when
the turn submitted it — a job that waited in the queue is priced against the model loaded now.
The alternative was giving the source its own `ContextBudget` and its own copy of the share,
which puts the budget in two places and makes the per-session share silently not apply to what
gets stored.

## Known limit — already written into ADR-026

Lossy by construction. A recap can say a duel happened; it cannot give back the exact line
someone swore. Layers 02–03 exist for that gap.

## Verification

- [x] Unit, layer 01 (`tests/unit/core/memory/test_rolling_summary_source.py`, 15 cases): a story
      inside the high-water mark is not summarized; what falls past it is folded once; **turn
      N+1 does not re-summarize**; a later pass folds only the turns the recap does not cover;
      the fold boundary never splits a turn; an over-budget recap is condensed and stored under
      budget; a shrunken budget condenses a recap with nothing new to fold; a summarizer that
      returns nothing leaves the recap alone.
- [x] Unit, **re-derivation** — the property the whole background design rests on. Running the
      job on turns 14 and 15 and running it only on turn 15 reach byte-identical stored state.
- [x] Unit, the worker (`tests/unit/infrastructure/test_asyncio_task_scheduler.py`, 7 cases): a
      duplicate key is dropped and a different session is not; the key frees up when the job
      ends; a job that raises is logged and the worker survives it; a full queue drops instead of
      blocking the turn; **shutdown cancels work in flight** rather than waiting 30 seconds for
      it.
- [x] Unit, the alarm: a recap behind the window edge logs the one warning ADR-026 asks for, and
      a caught-up recap logs nothing. It is checked **before** the fold, because the pass is
      about to close the gap — measured afterwards it would never fire.
- [x] Unit, budget contention: layer 01 is offered its share and layer 00 the whole remainder;
      `observe` hands each layer the budget it will have to fit; the recap survives contention
      with lore and loses to the window.
- [x] Unit, `ChatService`: a finished turn submits exactly one job, `/continue` and `/retry` do
      too, a failed turn submits none, and the submitted job really does run the pipeline's write
      half.
- [x] Contract + migration: the store contract passes against a real Postgres in both suites, and
      `20260810_0012` was verified `upgrade head` → `downgrade 20260802_0011` → `upgrade head`
      against a real database, with the columns asserted by name.
- [x] `uv run pytest` green (747 passed) · `uv run mypy src` clean · `uv run ruff check .` clean ·
      the admin panel type-checks and builds (`npm run build`).
- [ ] **Live over Telegram: still open.** Play past the window boundary and confirm the model
      still refers correctly to events no longer in the window. Carries over with S022's live
      run, which is Pablo's call.
- [ ] **Live: `/memory` off** and the recap disappears from the built prompt.
- [ ] **Live: restart the app while a summary job is in flight**, then play one more turn. The
      recap must catch up on its own, with no manual step.

## What this epic changed, in one paragraph

Long stories no longer lose their past. What the window drops is condensed in the background into
one recap that every later prompt carries, and the recap is kept short enough to stay affordable.
The background worker that makes it free on the turn path is now a shared piece of the engine:
S025 and S026 use the same queue, and any layer that plugs into it inherits the rule that keeps
it safe — a job is a question about stored state, never a command carrying data.

## Notes for S024 and S025

* The worker exists and is tested. A new layer needs no scheduling code of its own; it implements
  `observe` and the pipeline is already submitted once per turn.
* `MemoryObserveContext` now carries budgets. A layer that writes something the prompt must hold
  should read `source_budget` rather than work it out.
* `MemorySettings.budget_for` returns the whole remaining budget for a layer with no configured
  share. Layer 02 should decide whether it wants one; a lorebook that returns several fragments
  probably does.
* The `[Story So Far]` fragment is the first real body in the memory section, so the section's
  `label` then `body` rendering is now exercised in a live prompt rather than only in tests.
