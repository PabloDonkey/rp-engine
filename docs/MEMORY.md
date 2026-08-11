# Memory

How the engine decides what the model is allowed to remember.

> **Status: layers 00 and 01 are built.** ADR-026 accepted the architecture on 2026-08-02 and
> S021 settled the four open decisions on 2026-08-03. S022 built the token counter, the budget,
> the pipeline and layer 00 on 2026-08-10. S023 built the background worker and layer 01 on the
> same day. Layers 02 to 04 are still design; S024 to S026 build them, in that order.
>
> `DumpEverythingStrategy`, which put every message ever stored into every prompt, is gone.

Read ADR-026 for the decisions and the reasoning. This document is the working reference: what
each layer stores, what it returns, and what it costs.

---

## The shape

One port, five implementations, one composite.

```
ChatService
   └─ MemoryPipeline.recall(ctx)  ─┬─ RecentWindowSource      layer 00
                                   ├─ RollingSummarySource    layer 01
                                   ├─ LorebookSource          layer 02
                                   ├─ FactStateSource         layer 03
                                   └─ SemanticRecallSource    layer 04
                                        ↓
                                   MemoryFragment values, merged, ordered, cut to budget
                                        ↓
                                   ConversationBuilder renders one memory block
```

Every source implements `MemorySource`, which has two halves:

* **`recall`** runs before the prompt is built. It returns `MemoryFragment` values. It is on the
  turn path, so it must be fast.
* **`observe`** runs after a successful turn. The background worker runs it, so it never sits on
  the turn path and may be slow. `ChatService` submits one job per finished turn, keyed by
  session, and never waits for it.

The pipeline owns the budget, in both halves. A source reports what its fragment costs and is
told what it may spend. It never decides whether its fragment fits.

A source may have a **share** of the budget, held per session in `MemorySettings`. Layer 01 takes
a quarter by default. A source with no share gets what the other enabled shares leave, which is
what layer 00 gets, so the shares never have to add up to one.

The subtraction is what makes a share mean anything. Layer 00 would otherwise fill the budget
with turns on any long story, and every lower-priority fragment would then be dropped by the cut
below for want of room. The cost is that an unused share is wasted for that turn: a recap shorter
than its allowance leaves the difference unspent. A layer this build does not run reserves
nothing, so a session that switched on a layer against a newer build does not shrink the window
of an older one.

A source that fails does not fail the turn. The pipeline logs it, drops its fragments, and
carries on with the rest.

---

## The budget

The engine reads the loaded model's real context length from LM Studio at boot, then takes a
configured share of it. There is no hand-set token number, because a hand-set number goes
silently wrong the moment a model with a smaller window is loaded.

Token counts come from LM Studio's `count_tokens`, which uses the loaded model's own tokenizer.
The engine caches each count per message, keyed by model name. A character-ratio estimate takes
over if LM Studio cannot be reached, and logs that it did.

The memory budget is what the rest of the prompt leaves. Every turn, the prompt is built once
with no memory in it, priced, and the remainder handed to the pipeline. A long character card
and a stack of session rules therefore take room from the history, which no fixed reserve could
have known.

When the block is over budget, the pipeline cuts by fragment priority, dropping whole fragments.
What it dropped — how many stored turns did not reach the prompt, and the tokens in any fragment
that was cut — goes into the generation trace record, visible per message in the admin panel.
The dropped turns' own token total is deliberately not reported: the window stops counting at
the first message that does not fit, so a total would mean counting the whole history on every
turn, which is the cost the walk exists to avoid. It is not logged per turn, because with layer 01 off this happens on every turn of every
long session, and a warning that always fires is a warning nobody reads.

The one case that does get a warning: layer 01 is on and its summary is behind. That should never
happen, because the worker queues the summary at a high-water mark below the budget, not at the
budget.

---

## Layer 00 — recent window

**Shipped in S022.** Cannot be switched off. It is the conversation itself.

| | |
|---|---|
| Stores | nothing of its own. It reads `conversation_messages`. |
| `recall` returns | the most recent turns, word for word, cut to its token budget |
| `observe` does | nothing |
| Cost per turn | none beyond counting tokens |

It replaced `DumpEverythingStrategy`, which returned every message ever stored. The only real
change is that it stops at a budget.

It walks the stored turns from newest to oldest and keeps whole messages until the next one
does not fit. A message that alone exceeds the budget stops the walk rather than being skipped:
skipping it would put the turns on both sides of a missing turn into the prompt, which reads as
a story with a hole in it rather than a story that starts later.

Its fragment carries the turns themselves, not text. They reach the model as chat messages with
their own roles, which is what the assistant-role mapping (S017) and the prefill continuation
(S018) depend on.

**The floor.** When layer 01 is on, the window may not drop a message the summary does not yet
cover. `session_summaries.covers_through_turn` is that floor. When layer 01 is off there is no
floor, and dropped messages are simply gone from the prompt.

---

## Layer 01 — rolling summary

**Shipped in S023.** On by default. `LMStudioConversationSummarizer` was already written and
never wired in; S023 wired it and replaced its character-handoff prompt with two rolling-recap
prompts, one that folds new turns into the recap and one that condenses the recap itself.

| | |
|---|---|
| Stores | one row per session in `session_summaries` |
| `recall` returns | one fragment, labelled `[Story So Far]` |
| `observe` does | submits "is this session's summary behind?" to the worker |
| Cost per turn | none on the turn path. One model call every N turns, in the background. |

**How the worker decides.** It re-reads the transcript and `covers_through_turn`, then walks the
turns from newest to oldest to find two marks: the high-water mark (75% of the budget, set by
`RP_ENGINE_MEMORY_SUMMARY_HIGH_WATER_SHARE`) and the window edge. Everything past the high-water
mark that the recap does not yet cover is folded in, and the fold stops after a narrator reply so
a player line never lands in the recap while the answer to it stays in the window. When the recap
outgrows its own share of the budget, it is condensed once more — one pass, not a loop.

The job carries no message text — only the session id and the turn. That is what makes a job
lost to a restart harmless: the next turn asks the same question. Running the job late, twice, or
not at all all end in the same stored state, and there is a test that asserts exactly that.

**The alarm.** Before folding, the worker compares what the recap covered against what the window
could hold on the turn that just ran. If turns fell outside the window that the recap had not
reached, they reached the model through nothing at all, and that is the one memory warning
ADR-026 asks for. The high-water mark exists so it never fires.

**What it loses.** Exact wording. A summary is a paraphrase, so a line of dialogue the player
cares about will not come back the way it was said. That is what layers 02 and 04 cover.

---

## Layer 02 — lorebook

**Ships in S024.** Authored by hand, so a wrong result is a bug someone can point at rather than
a model that drifted.

| | |
|---|---|
| Stores | `lorebook_entries`, scoped to a scenario definition |
| `recall` returns | one fragment per matched entry, labelled `[Lore]`, ordered by priority |
| `observe` does | nothing. A person writes this layer. The engine never learns it. |
| Cost per turn | none. One indexed query. |

Entries carry trigger keys. `LorebookStore.find_matching(keywords)` matches them against the
recent messages using Postgres full-text search, so `dragons` matches `dragon`. Ranking happens
inside the repository — a deliberate exception to ADR-013, recorded in ADR-026, because the
alternative is loading the whole table into Python to rank it there.

Scenario authors and operators manage entries from the admin panel.

**What it misses.** Paraphrase that shares no stem with any key.

---

## Layer 03 — fact and state store

**Ships in S025.** The first layer that genuinely needs the background worker.

| | |
|---|---|
| Stores | `memory_facts` and `memory_fact_watermarks` |
| `recall` returns | one fragment holding the facts still valid for what is in scene |
| `observe` does | submits "which turns of this session have no facts yet?" |
| Cost per turn | none on the turn path. One extraction call per turn, in the background. |

**Never delete a fact.** Stamp `invalid_at` and record what replaced it in `superseded_by`. Append
without loss, consolidate later, never overwrite. Every serious memory system has converged on
this, and every one still finds it hard — the design study behind ADR-026 reports consolidation
accuracy between 14% and 60% across the systems it evaluated.

**Resolve conflicts deterministically first**, by subject and predicate slot. Ask the model only
when the deterministic rule cannot decide.

**What it does wrong.** It accumulates wrong facts. That is the known failure of every system in
this class, and it is why layer 01 ships first: there has to be something to fall back on.

---

## Layer 04 — semantic recall

**Deferred to S026, and only if a concrete failure demands it.**

| | |
|---|---|
| Stores | embeddings of summaries and extracted facts |
| `recall` returns | fragments ranked by similarity, keyword match and recency together |
| `observe` does | submits embedding work for anything new |
| Cost per turn | one embedding of the current message, plus one per stored chunk |

The cost is not the code. It is pgvector, which means new Postgres images for both docker compose
and the testcontainers fixture, plus a second model resident in video memory alongside the one
generating the story.

Postgres full-text search in layer 02 already closes most of the paraphrase gap for free. The
`EmbeddingProvider` port is designed now so that if this layer is ever needed, it is a migration
and an adapter rather than a redesign.

**Embed nothing raw.** This layer indexes summaries and extracted facts, which makes layer 03 a
prerequisite for it being any good.

---

## Per-session control

`MemorySettings` is a frozen value object on `ScenarioSession`, shaped like `SessionDirectives`.
It holds the enabled set and the per-source budget shares, and rides the session's existing JSONB
payload with no new column.

Layer 00 cannot be switched off, and the type makes that unrepresentable rather than merely
invalid. Layers 01 to 04 are per session. Defaults come from settings.

Players change them with `/memory`, next to `/rules` and `/director`: bare `/memory` lists the
layers and their state, and `/memory summary on|off` switches one. Operators switch the same
layers from the session page of the admin panel, which also shows the stored recap and how far it
reaches.

Under ADR-025, this is player-owned state: `/restart` carries it forward, `/clear` resets it.

---

## Adding a sixth layer

Write a class implementing `MemorySource`. Add it to the list in `app/main.py`. Add its toggle to
`MemorySettings`.

Nothing else changes. No existing source, no pipeline code, no builder code. That property is why
S021 wrote the contracts above down before anyone built a layer.

---

## The background worker

One `asyncio.Queue` inside the running process, owned by `app/lifespan.py` and started next to
the Telegram runtime. `ChatService` submits one job per finished turn and returns at once.

| Rule | Why |
|---|---|
| One job per session at a time; a duplicate is dropped | Two fast turns must not race over the same rows |
| Bounded queue; on overflow, log and drop | A backlog means the worker cannot keep up, which dropping shows and buffering hides |
| Cancelled on shutdown, never drained | Draining would hold a restart on a model call for work the next turn redoes |
| Every job wrapped; failures logged and swallowed | Nothing here is allowed to reach the player |

All four are safe for one reason: **a job is a question about stored state, never a command
carrying data.** Losing one costs nothing.
