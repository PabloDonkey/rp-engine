> 🗄️ **ARCHIVED — COMPLETED 2026-08-03.** Frozen; do not edit. Kept as evolution history.
> **Result:** the layered memory architecture is written down before any of it is built.
> ADR-026 landed 2026-08-02 with the `MemorySource` port, `MemoryFragment`, `MemoryPipeline`,
> per-session `MemorySettings` and the S022→S026 build order. On 2026-08-03 the four decisions
> the ADR delegated here were settled and written into it: an in-process `asyncio.Queue` owned
> by `app/lifespan.py`, safe without durability because **a job is a question about stored
> state, never a command carrying data**; LM Studio's own `count_tokens` as the counter, cached
> per message and keyed by model name, with the budget read from `get_context_length()` at boot
> instead of configured; budget overflow recorded in the generation trace rather than logged per
> turn; and two frozen read models, so no source ever sees the live `ScenarioSession`.
> `ARCHITECTURE.md` lost the "Memory Manager" that ADR-013 forbade. `docs/MEMORY.md` is new.
> No code changed — S022 unblocked, S023 gained the worker as scope.

# S021 · Memory architecture — ADR-026 and the design docs

**Status:** ✅ COMPLETE (2026-08-03)
**Effort:** ~1 day. Design only, no code.
**Risk:** Low to build, high to get wrong. Five sources will depend on the contracts written here.
**Design source:** [Five ways to remember a story](https://claude.ai/code/artifact/c77560f4-99c2-4566-8b1c-9687d3893ac5)
— Pablo's chosen architecture. ADR-026 cites it.
**Layout study:** [Memory in the hexagon](https://claude.ai/code/artifact/798a0d4a-c578-4de7-8ee9-4550fbfebcb5)
— where each piece lands in the ports-and-adapters layout, and the four open decisions.

## Goal

Write the memory architecture down before any of it is built. The toggle architecture, the
fragment contract and the budget rules are expensive to change once five sources depend on them,
and cheap to get right on paper.

## Tasks

- [x] **ADR-026** in `docs/adr/0026-layered-memory.md` — the `MemorySource` port, `MemoryFragment`,
      `MemoryPipeline`, per-session `MemorySettings`, the five layers, the build order
      S022→S026, the deferred embedding decision, and the partial supersession of ADR-013.
- [x] **`ARCHITECTURE.md`** — "Memory Manager" replaced by `MemoryPipeline`, plus new sections for
      the background worker and the token counter. The builder now receives fragments as data.
- [x] **`DOMAIN_MODEL.md`** — `MemorySettings`, `MemoryFragment`, `MemoryRecallContext` and
      `MemoryObserveContext`, all marked planned.
- [x] **`DATABASE_MODEL.md`** — `session_summaries`, `lorebook_entries`, `memory_facts` and
      `memory_fact_watermarks`, plus the note that `MemorySettings` adds no column.
- [x] **Per-source specs** — new `docs/MEMORY.md`, one section per layer. Added to the
      documentation map in `CLAUDE.md`.
- [x] **`ROADMAP.md`** — Milestone 4 rewritten around the five layers and the S022 to S026 order.

## Decisions ADR-026 left to this epic — all settled 2026-08-03

Recorded in ADR-026, section "Decisions delegated to S021, now settled".

- [x] **Background worker.** An in-process `asyncio.Queue`, owned by `app/lifespan.py`, wrapping
      `MemoryPipeline.observe` once in the application layer. **The rule that makes it safe: a job
      is a question about stored state, never a command carrying data.** A job lost to a restart
      costs nothing, so no jobs table, no lease, no retry policy. Rejected `asyncio.create_task`
      inside `ChatService` and a Postgres jobs table. Lands in S023.
- [x] **Token counter.** LM Studio's own `count_tokens`, cached per message and keyed by model
      name. The budget is read from `get_context_length()` at boot, not configured — only the
      share of it is a setting. Character-ratio fallback behind the same port. No new dependency.
- [x] **Window overflow.** Into the generation trace record, which already takes a free-form dict
      and is already rendered per message in the admin panel. No per-turn log line, because with
      layer 01 off this happens every turn and would become noise. A warning is reserved for the
      real alarm: layer 01 on and its summary behind. Accepted cost — the player is never told.
- [x] **What `recall` receives.** A frozen `MemoryRecallContext`, never the live `ScenarioSession`.
      `observe` gets a separate `MemoryObserveContext` holding identifiers only, because it runs in
      the background and must carry nothing that can go stale. No entity resolution until S025
      needs it.

Also recorded in ADR-026: layer 02 ranks trigger keys inside `LorebookStore.find_matching`, which
is a deliberate exception to ADR-013's storage-versus-selection split. Written down so the next
reader does not read it as an accident.

## Verification

Design epic, so the bar is review, not tests.

- [x] The ADR and the docs agree with each other. One name per thing — grep confirms no
      `SummaryMemorySource` / `WindowMemorySource` survivors, and every remaining "memory manager"
      hit is ADR-013's own text or ADR-026 quoting it.
- [x] `uv run pytest tests/unit/docs/test_adr_files.py` — 158 passed. Front matter and the
      supersession back links still hold after the amendment.
- [x] Every claim about current code was checked against the code in this session: `lifespan.py`,
      `main.py:134`, `generation_trace_store.py`, and the LM Studio SDK line numbers.
- [x] `ste-lint` on the touched files. **Every one improved against its pre-edit baseline:**
      ADR-026 2.08 → 1.98, `ARCHITECTURE.md` 2.99 → 2.78, `DATABASE_MODEL.md` 3.37 → 3.09,
      `DOMAIN_MODEL.md` 3.88 → 3.44, `ROADMAP.md` 2.46 → 2.31. New `MEMORY.md` is at **1.71**.
      Only the new file and ADR-026 are under 2.0; the four older documents were already above it
      before this epic, and rewriting them whole was out of scope.
- [x] `uv run ruff check .` clean. `uv run mypy src` clean (106 files). No `src/` change was made.

**Known, not caused here:** `tests/unit/infrastructure/test_settings.py::test_scenario_catalog_dirs_defaults_to_data_catalog`
fails locally because the developer `.env` sets `RP_ENGINE_SCENARIO_CATALOG_DIRS` and the test does
not isolate the environment. `uv run mypy .` also reports 148 errors, all inside `tests/`. Both
predate this epic, which changed no code.
