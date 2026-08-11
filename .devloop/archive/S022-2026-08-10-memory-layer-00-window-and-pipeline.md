> 🗄️ **ARCHIVED — COMPLETED 2026-08-10.** Frozen; do not edit. Kept as evolution history.
> **Result:** `DumpEverythingStrategy` is gone. Every turn prices its own prompt — built once
> with no memory in it and counted with the model's own tokenizer — then hands what is left to
> `MemoryPipeline`, which returns the newest whole turns that fit. Landed with it: the
> `MemorySource` port, `MemoryFragment`, the two frozen read models, the pipeline (sources run
> together, whole fragments cut by priority, a failing layer never fails the turn),
> `RecentWindowSource`, and `MemorySettings` on the session with **no migration** — it rides in
> the `directives` JSONB column, and its type makes "layer 00 off" a compile error rather than a
> rule to remember. With only layer 00 enabled the prompt **text** is unchanged, so the one new
> behaviour is that a long story stops growing the prompt without limit.
> **Fixed on the way:** the generation trace read its prompt sections by *position* and was
> already reporting the scenario intro as the character card; every system message now carries a
> `prompt_section` label.
> **Two deliberate deviations from ADR-026**, both argued in Scope below: `MemoryFragment` gained
> a `messages` field, and the dropped messages' token total is not reported.
> **Verified live against the loaded model** (real 32768-token window, real token counts).
> **Not verified over Telegram** — that check is still open. See Verification.

# S022 · Memory layer 00 — token budget, windowed recall, pipeline skeleton

**Status:** ✅ COMPLETE — 2026-08-10. Every scope item is built and tested. The one open item is the live Telegram run, see Verification.
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

- [x] `MemorySource` protocol (`recall` read half / `observe` write half) in
      `core/ports/memory_source.py` + frozen `MemoryFragment` in `core/memory/fragment.py`.
      **One field more than ADR-026 fixed:** `messages`, empty for every layer but 00. Layer 00
      recalls the conversation itself, which has to reach the model as chat turns with their own
      roles — flattening it into prompt text would undo the assistant-role mapping (S017) and the
      prefill continuation built on it (S018). Such a fragment leaves `body` empty and the budget
      treats it exactly like any other. The alternative, a second return type for layer 00, would
      have split the one port ADR-026 exists to keep.
- [x] Frozen `MemoryRecallContext` and `MemoryObserveContext` in `core/memory/recall_context.py`,
      with the fields ADR-026 lists. A source never receives the live `ScenarioSession`, and
      `observe` carries identifiers only. `MemoryRecall`, the pipeline's own return value, lives
      beside them.
- [x] `MemoryPipeline` composite (`core/memory/pipeline.py`): runs the enabled sources with
      `asyncio.gather`, merges fragments, drops whole fragments lowest-priority-first until the
      block fits. A failing source is logged and dropped, never fatal to the turn — both halves,
      `recall` and `observe`.
- [x] `RecentWindowSource` — walks newest to oldest and keeps whole messages until the next one
      does not fit. A message that alone exceeds the budget **stops** the walk instead of being
      skipped: skipping it would put the turns on both sides of a missing turn into the prompt,
      which reads as a story with a hole in it. Its floor is `session_summaries.covers_through_turn`
      once S023 lands; until then there is no floor.
- [x] What the budget cut goes into the generation trace `record` dict under a `memory` key
      (`budget_tokens`, `used_tokens`, `dropped_messages`, `dropped_fragment_tokens`), not into a
      per-turn log line. **One deviation:** the dropped *messages'* token total is not reported.
      The window stops counting at the first message that does not fit, so a total would mean
      counting the whole history on every turn — the exact cost the walk exists to avoid. The
      count is the number that says story left the prompt; every number reported is exact.
- [x] The memory budget is what the rest of the prompt leaves. `ChatService._recall` builds the
      prompt once with no memory in it, prices it with the `TokenCounter`, and hands the remainder
      to the pipeline. A fixed reserve could not know that a long character card and ten session
      rules leave less room for history.

### 3. Replace `MemoryStrategy`

- [x] `MemoryStrategy` and `DumpEverythingStrategy` are deleted, along with the strategy's unit
      test. `RecentWindowSource` covers it in spirit: with a budget larger than the story, it
      returns the same list.
- [x] All four call sites in `chat_service.py` and the wiring in `app/main.py` now go through
      `MemoryPipeline`. `ChatService` takes a `memory_pipeline` and a `token_counter`.
- [x] ADR-013's separation holds: the pipeline composes strategies and never persists a
      conversation.

### 4. Prompt assembly

- [x] The hardcoded one-liner is now `MEMORY_HINT`, and the memory section renders the fragments
      when there are any. With only layer 00 enabled there are none — layer 00 returns turns, not
      text — so **the prompt is unchanged by this epic apart from the window**. That is deliberate:
      it keeps the risk of this epic in the budget, not in the wording.

### 5. Per-session settings

- [x] Frozen `MemorySettings` on `ScenarioSession` (`core/memory/settings.py`), mirroring
      `SessionDirectives`, with `with_source_enabled` / `with_source_disabled` returning new
      instances. **Per-source budgets are deliberately not built** (YAGNI): no second source
      exists to contend for the budget yet, so the field would be an abstraction to maintain for
      nothing. S023 adds it with the first source that needs it.
- [x] No new column. It rides inside the `directives` JSONB column under a `memory` key. The two
      share a column because they share a lifecycle — both are player-owned state under ADR-025.
      A row written before S022 has no `memory` key and loads with the defaults.
- [x] Layer 00 is not toggleable, and the type says so: `enabled_sources` is typed
      `ToggleableMemorySystemId`, a `Literal` that does not contain `recent_window`. "Layer 00
      off" is a type error, not a rule someone has to remember to check (ADR-026 rule 5).
- [x] `/restart` carries the settings forward and `/clear` resets them, through the existing
      `PlaythroughService._reset(carry_player_state=...)` path.

### 6. Fix first, not after

- [x] **Fixed first, before the builder changed.** The method is `_serialize_prompt`, not
      `_build_debug_prompts` — the epic named it from the ADR, and the ADR named it wrong. Every
      system message now carries a `prompt_section` label written by the builder, and the trace
      reads sections by label. The indices were indeed already wrong: with a scenario that has an
      overview, slot 0 was the scenario intro, so the trace reported the intro as the character
      card. Two keys were added while the reader was honest about what it holds:
      `scenario_rules` and `memory_section`.

## Verification

- [x] Unit: a session longer than the budget yields a context that fits, newest-first, with no
      partial message (`tests/unit/core/memory/test_recent_window_source.py`, 11 cases); budget
      contention between two sources resolves by `priority`, and the recent window is never the
      fragment dropped (`tests/unit/core/memory/test_pipeline.py`, 10 cases).
- [x] Unit: `MemorySettings` round-trips through `scenario_serialization.py` at 0/1/N enabled
      sources; a pre-S022 payload loads with defaults; an unknown layer name is dropped rather
      than kept. The Postgres store contract covers the same round trip against a real database.
- [x] The debug-prompt fix has a test that fails against the positional slicing — checked by
      putting the old code back and watching it fail, then removing it again.
- [x] `uv run pytest` green (683 passed) · `uv run mypy .` clean for `src/` · `uv run ruff check .`
      clean.
- [x] **Live against the real model** (2026-08-10, `gemma-4-26b-a4b-it-heretic` as loaded in LM
      Studio): `get_context_length()` returned **32768**, so the budget at share 0.7 was **22937**
      tokens — no fallback, no guess. `count_tokens` returned 17 for a 75-character sentence,
      against the character-ratio fallback's estimate of 19, so the fallback errs high, which is
      the safe direction. With 137 tokens left after the rest of the prompt, a 120-turn story
      replayed its newest **5** turns for 135 tokens and dropped 115. Nothing went over budget and
      no message was cut in half.
- [ ] **Live over Telegram: still open.** Run a real session past the budget and confirm the reply
      stays in character and no `context_length` finish reason appears. Needs the bot running,
      which is Pablo's call, so it carries over the same way S027's live check did.

## Questions S021 settled (2026-08-03)

All four are answered in ADR-026, section "Decisions delegated to S021, now settled". Nothing in
this epic is blocked on a decision any more.

| Question | Answer |
|---|---|
| Token counter | LM Studio `count_tokens`, cached per message and keyed by model name. Budget read from `get_context_length()` at boot. |
| Window overflow | Into the generation trace record. No per-turn log line. |
| What `recall` receives | A frozen `MemoryRecallContext`, never the live session. `observe` gets identifiers only. |
| Background worker | An in-process `asyncio.Queue` owned by `app/lifespan.py`. Not needed by this epic; S023 lands it. |

## What this epic changed, in one paragraph

`DumpEverythingStrategy` is gone. Every turn now prices its own prompt, hands what is left to
`MemoryPipeline`, and gets back the newest turns that fit. With only layer 00 enabled the prompt
text is unchanged — the same sections, the same memory hint — so the only new behaviour is that a
long story stops growing the prompt without limit. Layers 01 to 04 plug into the pipeline with a
class and one line in `app/main.py`.

## Notes for S023

* `MemoryPipeline.observe` exists and is tested, but **nothing calls it yet**. S023 owns the
  background worker that does, per ADR-026 decision 1.
* Per-source token budgets on `MemorySettings` are not built. S023 is the first epic with two
  sources that can contend, so it adds them.
* Every source is currently offered the *whole* remaining budget and they run at the same time,
  so the sum can exceed it; the priority cut is what resolves that. With a second source this is
  worth revisiting against fixed shares.
* The memory section of the prompt renders fragments as `label` then `body`, joined by a blank
  line. `[Story So Far]` is the first real one.
