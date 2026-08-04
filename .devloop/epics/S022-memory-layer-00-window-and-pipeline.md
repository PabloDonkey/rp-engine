# S022 · Memory layer 00 — token budget, windowed recall, pipeline skeleton

**Status:** 🟢 In progress — scope item 1 (token counting) done 2026-08-03.
**Depends on:** **S021** — ADR-026 + memory design docs. Do not start this before the ports and
the fragment contract are written down; this epic implements them, it does not decide them.
**Design source:** [Five ways to remember a story](https://claude.ai/code/artifact/c77560f4-99c2-4566-8b1c-9687d3893ac5)
— Pablo's chosen memory architecture. ADR-026 must cite this link.
**Effort:** ~2 days
**Risk:** Medium — touches the prompt of every turn. A wrong budget silently drops story.

## Problem

The engine has no memory system, only a full replay. `DumpEverythingStrategy.build_context`
([dump_everything_strategy.py:6](../../src/rp_engine/core/memory/dump_everything_strategy.py#L6))
returns `list(messages)` — every message ever stored, verbatim. Nothing counts tokens against a
budget. The engine learns it overflowed **after** the call, when the provider reports
`finish_reason == "context_length"`
([provider.py:407](../../src/rp_engine/infrastructure/llm/lmstudio/provider.py#L407)).

`RP_ENGINE_LMSTUDIO_MAX_TOKENS` caps *generated output*, not input context. There is no context
budget setting at all.

## Goal

Layer 00 of the five-layer design: a budgeted recent window, plus the pipeline that layers 01–04
plug into. After this epic, long sessions stop overflowing, and adding layer 01 is one new class.

## Scope

### 1. Token counting (the prerequisite for every layer)

**Settled in S021** (ADR-026 → "Decisions delegated to S021"): ask LM Studio, cache the answer.

- [x] `TokenCounter` port in `core/ports/`, one method (`core/ports/token_counter.py`).
- [x] `LMStudioTokenCounter` in `infrastructure/` — the software development kit (SDK) already
      exposes `count_tokens(input) -> int` on the model handle
      (`.venv/lib/python3.12/site-packages/lmstudio/async_api.py:1130`), which counts with the
      loaded model's own tokenizer. **No new dependency.**
- [x] Cache the count per message, keyed by **model name** — a stored message never changes, but
      its token count changes when the model does. In-memory first; a `token_count` column is
      deliberately deferred (see `docs/DATABASE_MODEL.md`). Bounded least-recently-used cache,
      4096 entries, keyed by model name and a digest of the text. A fallback estimate is never
      cached, so the next call asks LM Studio again.
- [x] Character-ratio fallback behind the same port, which logs when it fires. A hiccup talking to
      localhost must never fail a turn. `core/memory/character_ratio_token_counter.py`, four
      characters per token, rounding up.
- [x] Read the total budget from `get_context_length()` at boot (same file, line 1135) and take a
      configured **share** of it. The share is the setting; the absolute token number is not.
      Follow the `RP_ENGINE_`-prefixed pydantic-settings pattern in
      `infrastructure/config/settings.py`.
      Landed as a second one-method port, `ContextWindowProbe` (`LMStudioTokenCounter` implements
      both), plus `ContextBudget` in `core/memory/`. Settings:
      `RP_ENGINE_MEMORY_CONTEXT_BUDGET_SHARE` (0.7) and `RP_ENGINE_MEMORY_FALLBACK_CONTEXT_LENGTH`
      (4096, used only when LM Studio cannot be asked at all). `app/lifespan.py` resolves and logs
      the budget at boot, so a wrong one shows up there rather than in a silently trimmed prompt.

**Also fixed here (test pollution, found on the way):** `alembic/env.py` called
`fileConfig(...)` with the default `disable_existing_loggers=True`, which switched off the whole
`rp_engine` logger tree for every test that ran after the migration tests. Any test asserting on
a log line passed alone and failed in a full run. Now `disable_existing_loggers=False`.

### 2. The pipeline and its port

- [ ] `MemorySource` protocol (`recall` read half / `observe` write half) + frozen `MemoryFragment`
      (`source`, `label`, `body`, `priority`, `tokens`) — exactly as ADR-026 fixes them.
- [ ] Frozen `MemoryRecallContext` (session id, scenario id, recent messages, current user message,
      remaining budget) and `MemoryObserveContext` (session id, scenario id, turn). **Settled in
      S021:** a source never receives the live `ScenarioSession`, and `observe` carries identifiers
      only — never message text, because it runs in the background worker.
- [ ] `MemoryPipeline` composite: runs the enabled sources concurrently, merges fragments, applies
      the budget by `priority`. A failing source is logged and dropped, never fatal to the turn.
- [ ] `RecentWindowSource` — the last N turns that fit the allowance. Its floor is
      `session_summaries.covers_through_turn` once S023 lands; until then there is no floor.
- [ ] **Settled in S021:** what the budget cut — dropped message count and token total — goes into
      the generation trace `record` dict (`GenerationTraceStore.append`), not into a per-turn log
      line. A warning is reserved for the S023 case where layer 01 is on and its summary is behind.

### 3. Replace `MemoryStrategy`

- [ ] The existing port is too thin: `build_context(messages) -> messages`, sync, with no session,
      no scenario and no budget
      ([memory_strategy.py:6](../../src/rp_engine/core/ports/memory_strategy.py#L6)).
- [ ] Four call sites in `chat_service.py` (lines 117, 205, 300, 309) and one wiring line in
      `app/main.py:134`.
- [ ] Keep ADR-013's separation of conversation *storage* from context *strategy*. Delete
      `DumpEverythingStrategy` and its unit test only once the window source passes them in spirit.

### 4. Prompt assembly

- [ ] `ConversationBuilder` emits a hardcoded one-liner today —
      `"Use conversation history to keep continuity and character consistency."`
      ([builder.py:288](../../src/rp_engine/core/conversation/builder.py#L288)). That line becomes the
      rendered fragment block. Keep it as the fallback when no source returns anything.

### 5. Per-session settings

- [ ] Frozen `MemorySettings` on `ScenarioSession`, mirroring `SessionDirectives`: enabled set +
      per-source budgets, `with_*` transitions returning new instances.
- [ ] Rides the existing session JSONB payload — **no new column**, same degrade-to-default
      deserialization that keeps old exports loadable.
- [ ] Layer 00 is not toggleable: it *is* the conversation. Only 01–04 can be switched off.

### 6. Fix first, not after

- [ ] **Latent bug in the way.** `_build_debug_prompts` slices system messages positionally —
      slot 0 = character, 1 = world, 2 = rules
      ([chat_service.py:640-642](../../src/rp_engine/application/services/chat_service.py#L640-L642)).
      Those indices are **already wrong** (S014 inserted language / rules / director sections ahead
      of them), and a memory section shifts them again. Fix before touching the builder.

## Verification

- [ ] Unit: a session longer than the budget yields a context that fits, newest-first, with no
      partial message; budget contention between two sources resolves by `priority`.
- [ ] Unit: `MemorySettings` round-trips through `scenario_serialization.py` at 0/1/N enabled
      sources; a pre-S022 payload loads with defaults.
- [ ] The debug-prompt fix has a test that fails against the current positional slicing.
- [ ] `uv run pytest` green · `uv run mypy .` clean · `uv run ruff check .` clean.
- [ ] **Live over Telegram:** run a session past the budget and confirm the reply stays in
      character and no `context_length` finish reason appears.

## Questions S021 settled (2026-08-03)

All four are answered in ADR-026, section "Decisions delegated to S021, now settled". Nothing in
this epic is blocked on a decision any more.

| Question | Answer |
|---|---|
| Token counter | LM Studio `count_tokens`, cached per message and keyed by model name. Budget read from `get_context_length()` at boot. |
| Window overflow | Into the generation trace record. No per-turn log line. |
| What `recall` receives | A frozen `MemoryRecallContext`, never the live session. `observe` gets identifiers only. |
| Background worker | An in-process `asyncio.Queue` owned by `app/lifespan.py`. Not needed by this epic; S023 lands it. |
