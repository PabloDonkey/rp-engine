# S023 · Memory layer 01 — rolling summary

**Status:** 🔵 Backlog (not started)
**Depends on:** **S022** (the pipeline, the token counter, the `MemorySource` port) → which depends
on **S021** (ADR-026).
**Design source:** [Five ways to remember a story](https://claude.ai/code/artifact/c77560f4-99c2-4566-8b1c-9687d3893ac5)
— Pablo's chosen memory architecture. ADR-026 must cite this link.
**Effort:** ~1–2 days
**Risk:** Low-to-medium — no new infrastructure; the risk is summary drift, not breakage.

## Problem

Layer 00 keeps a budgeted window, so everything older than the window is simply gone. The story so
far disappears with no trace. This is the layer that catches it.

## Goal

Every N turns, condense what fell out of the window into a running recap, and re-condense recaps
when they grow too long. Injected on every turn as "the story so far".

Highest continuity gain per unit of work available in this codebase, and it needs **no new
infrastructure of any kind**.

## Head start already in the repo

`LMStudioConversationSummarizer`
([conversation_summarizer.py](../../src/rp_engine/infrastructure/llm/lmstudio/conversation_summarizer.py))
and its port `ConversationSummarizer` are **fully implemented and never wired into the composition
root** — dead code today. The prompt is already tuned for roleplay continuity ("use only
information present in the transcript", "no invented facts", 50–150 words, `temperature=0.2`).

Caveat: it was written for a *character handoff* (`metadata={"purpose": "character_switch_summary"}`,
and `_format_recent_messages` labels every non-user message `Character`). It needs a rolling-recap
prompt variant, not a straight reuse.

## Scope

- [ ] **The background worker itself** — settled in S021, and this epic is where it lands. In-process
      `asyncio.Queue`, `BackgroundTaskScheduler` port in `core/ports/`, `AsyncioTaskScheduler` in
      `infrastructure/`, started and cancelled by `app/lifespan.py` next to `TelegramRuntime`, plus
      an inline fake for tests. Dedupe by `(session_id, source_id)`; bounded queue; cancel on
      shutdown rather than drain; every job wrapped so a failure never reaches the turn. See
      ADR-026 for the full rules.
- [ ] `RollingSummarySource(MemorySource)` in `core/memory/`:
      - `recall` → one `[Story So Far]` fragment, priority above the window's oldest turns.
      - `observe` → submits the question "is this session's summary behind?". It carries the
        session id and turn only. **Never message text** — a job that carries data is wrong when it
        is delayed, instead of merely late.
- [ ] Queue at a **high-water mark below the budget** (start at 75%), not at the budget. The
      summary then lands while the window still has room, so the window never has to drop a message
      the summary does not cover. Overflow becomes an alarm rather than routine.
- [ ] Re-condense: when the stored summary itself exceeds its budget, summarize the summary.
      Community guidance is ~40–50 turns per recap and keep it short — recent, clearly stated
      detail beats a long buried one.
- [ ] Persistence: **one new table**, `session_summaries` — see `docs/DATABASE_MODEL.md` for the
      columns. `covers_through_turn` is the load-bearing one: it is both the window's floor and the
      answer the worker re-reads. Alembic migration, reversible, verified `upgrade head` *and*
      `downgrade` against a real Postgres.
- [ ] Store contract test alongside the existing suites in `tests/.../contracts/`.
- [ ] Wire `LMStudioConversationSummarizer` into `app/main.py` (it has never been wired).
- [ ] Give the summarizer a rolling-recap prompt distinct from the character-handoff one.
- [ ] First real entry in the per-session toggle: `/memory` command alongside `/rules` and
      `/director`, plus an admin-panel toggle.

### Settled in S021 (2026-08-03) — no design call left here

**Background, not inline.** An in-process queue owned by `app/lifespan.py`, not an
`asyncio.create_task` in the chat service. The scheduler wraps `MemoryPipeline.observe` once in
the application layer; the source itself knows nothing about background execution.

The rule that makes an in-memory queue safe: **a job is a question about stored state, never a
command carrying data.** A job lost to a restart costs nothing, because the next turn asks the
same question. That is why this needs no jobs table, no lease and no retry policy.

## Known limit — already written into ADR-026

Lossy by construction. A summary can tell the model a duel happened; it cannot give back the exact
line someone swore. That gap is what layers 02–03 exist for; do not try to close it here by making
summaries longer.

## Verification

- [ ] Unit: N turns of history produce exactly one recap; turn N+1 does not re-summarize; an
      over-budget summary is re-condensed and stays under budget.
- [ ] Unit (worker): a submit for a `(session, source)` key that already has a job in flight is
      dropped; a job that raises is logged and does not propagate; shutdown cancels in flight work
      without waiting for it.
- [ ] Unit (re-derivation): dropping the job entirely leaves the next turn's `observe` producing
      the same summary. This is the property the whole design rests on — test it directly.
- [ ] Unit: the summary fragment survives budget contention with the window (priority order).
- [ ] Migration reversibility against a real Postgres, in `test_migration_integrity_postgres.py`.
- [ ] `uv run pytest` green · `uv run mypy .` clean · `uv run ruff check .` clean.
- [ ] **Live over Telegram:** play past the window boundary and confirm the model still refers
      correctly to events that are no longer in the window.
- [ ] **Live:** `/memory` toggles the layer off and the recap disappears from the built prompt.
- [ ] **Live:** restart the app while a summary job is in flight, then play one more turn. The
      summary must catch up on its own, with no manual step.
