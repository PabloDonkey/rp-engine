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

- [ ] `SummaryMemorySource(MemorySource)` in `core/memory/`:
      - `recall` → one `[Story So Far]` fragment, priority above the window's oldest turns.
      - `observe` → after a successful turn, summarize if N turns have passed since the last recap.
- [ ] Re-condense: when the stored summary itself exceeds its budget, summarize the summary.
      Community guidance is ~40–50 turns per recap and keep it short — recent, clearly stated
      detail beats a long buried one.
- [ ] Persistence: **one new table** for per-session summaries (turn range covered, body, token
      count, created_at). Alembic migration, reversible, verified `upgrade head` *and* `downgrade`
      against a real Postgres.
- [ ] Store contract test alongside the existing suites in `tests/.../contracts/`.
- [ ] Wire `LMStudioConversationSummarizer` into `app/main.py` (it has never been wired).
- [ ] Give the summarizer a rolling-recap prompt distinct from the character-handoff one.
- [ ] First real entry in the per-session toggle: `/memory` command alongside `/rules` and
      `/director`, plus an admin-panel toggle.

### Design call to make before coding

**Inline or background?** Summarizing inline means a visible pause every N turns. Background means
an `asyncio.create_task` in the chat service or a new runtime component in the lifespan — the repo
has no job runner. S025 (layer 03) needs a real background worker anyway; decide here whether to
build it now or accept the pause.

## Known limit — write it into ADR-026

Lossy by construction. A summary can tell the model a duel happened; it cannot give back the exact
line someone swore. That gap is what layers 02–03 exist for; do not try to close it here by making
summaries longer.

## Verification

- [ ] Unit: N turns of history produce exactly one recap; turn N+1 does not re-summarize; an
      over-budget summary is re-condensed and stays under budget.
- [ ] Unit: the summary fragment survives budget contention with the window (priority order).
- [ ] Migration reversibility against a real Postgres, in `test_migration_integrity_postgres.py`.
- [ ] `uv run pytest` green · `uv run mypy .` clean · `uv run ruff check .` clean.
- [ ] **Live over Telegram:** play past the window boundary and confirm the model still refers
      correctly to events that are no longer in the window.
- [ ] **Live:** `/memory` toggles the layer off and the recap disappears from the built prompt.
