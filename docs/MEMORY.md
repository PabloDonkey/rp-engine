# Memory

How the engine decides what the model is allowed to remember.

> **Status: design.** ADR-026 accepted the architecture on 2026-08-02 and S021 settled the four
> open decisions on 2026-08-03. None of it is built. S022 to S026 build it, in that order.
>
> Today `DumpEverythingStrategy` puts every message ever stored into every prompt, and nothing
> counts tokens. That is the problem this design replaces.

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
  the turn path and may be slow.

The pipeline owns the budget. A source reports what its fragment costs. It never decides whether
its fragment fits.

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

When the block is over budget, the pipeline cuts by fragment priority. What it dropped — message
count and token total — goes into the generation trace record, visible per message in the admin
panel. It is not logged per turn, because with layer 01 off this happens on every turn of every
long session, and a warning that always fires is a warning nobody reads.

The one case that does get a warning: layer 01 is on and its summary is behind. That should never
happen, because the worker queues the summary at a high-water mark below the budget, not at the
budget.

---

## Layer 00 — recent window

**Ships in S022.** Cannot be switched off. It is the conversation itself.

| | |
|---|---|
| Stores | nothing of its own. It reads `conversation_messages`. |
| `recall` returns | the most recent turns, word for word, cut to its token budget |
| `observe` does | nothing |
| Cost per turn | none beyond counting tokens |

It replaces `DumpEverythingStrategy`, which returns every message ever stored. The only real
change is that it stops at a budget.

**The floor.** When layer 01 is on, the window may not drop a message the summary does not yet
cover. `session_summaries.covers_through_turn` is that floor. When layer 01 is off there is no
floor, and dropped messages are simply gone from the prompt.

---

## Layer 01 — rolling summary

**Ships in S023.** The best value in the stack: `LMStudioConversationSummarizer` and its port are
already written, and the composition root has never wired them in.

| | |
|---|---|
| Stores | one row per session in `session_summaries` |
| `recall` returns | one fragment, labelled `[Story So Far]` |
| `observe` does | submits "is this session's summary behind?" to the worker |
| Cost per turn | none on the turn path. One model call every N turns, in the background. |

**How the worker decides.** It reads `covers_through_turn`, compares it with the conversation,
and measures what falls outside the window budget. If the window has passed its high-water mark
(start at 75%), it condenses the next stretch and moves the watermark. When the summary itself
outgrows its own budget, it condenses the summary again.

The job carries no message text — only the session id and the turn. That is what makes a job
lost to a restart harmless: the next turn asks the same question.

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
It holds the enabled set and the per-source budgets, and rides the session's existing JSONB
payload with no new column.

Layer 00 cannot be switched off, and the type makes that unrepresentable rather than merely
invalid. Layers 01 to 04 are per session. Defaults come from settings.

Players change them with `/memory`, next to `/rules` and `/director`. Operators change them from
the admin panel.

Under ADR-025, this is player-owned state: `/restart` carries it forward, `/clear` resets it.

---

## Adding a sixth layer

Write a class implementing `MemorySource`. Add it to the list in `app/main.py`. Add its toggle to
`MemorySettings`.

Nothing else changes. No existing source, no pipeline code, no builder code. That property is why
S021 wrote the contracts above down before anyone built a layer.
