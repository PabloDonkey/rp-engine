---
id: ADR-026
title: "Layered Memory: One Port, Five Sources, Per-Session Toggles"
status: accepted
created: 2026-08-02
supersedes: [ADR-013]
superseded_by: []
---

# ADR-026 — Layered Memory: One Port, Five Sources, Per-Session Toggles

**Scope:** design only. No code yet. S021 wrote this. S022 to S026 build it.

**Design source:** [Five ways to remember a story](https://claude.ai/code/artifact/c77560f4-99c2-4566-8b1c-9687d3893ac5).
This is the study the architecture comes from. It holds the full comparison, the cost of each
layer in this codebase, and the sources behind the research claims quoted below.

---

## Context

The engine has no memory system. It has a full replay.

`DumpEverythingStrategy.build_context` returns `list(messages)`. Every message ever stored goes
into every prompt. Nothing counts tokens against a budget. The only token-like measure in the
repository is `len(text.split())`, and it only decorates a debug trace. The engine learns that it
overflowed the context window after the call, when the provider reports
`finish_reason == "context_length"`.

`RP_ENGINE_LMSTUDIO_MAX_TOKENS` caps generated output. It does not cap input context. No context
budget setting exists.

The prompt already reserves the slot. `ConversationBuilder` emits one hardcoded sentence between
the director instructions and the history: "Use conversation history to keep continuity and
character consistency." That line is where every memory layer lands.

Three things are already in the repository and unused.

1. `LMStudioConversationSummarizer` and its port are complete. The composition root never wires
   them. The prompt inside is tuned for roleplay continuity.
2. `scenario_sessions.world_state` and `scenario_sessions.story_progress` are persisted JavaScript
   Object Notation Binary (JSONB) columns that nothing reads.
3. `SessionDirectives` is the exact shape the per-session memory toggles should copy.

ADR-013 blocks the work as written. It pins the engine to `DumpEverythingStrategy`, forbids
summarization, retrieval and embeddings, and forbids a generic memory manager. Those rules are
scoped to Milestone 2. `ARCHITECTURE.md` already describes a "Memory Manager" that ADR-013 rules
out. This ADR resolves that conflict on purpose rather than by drift.

## Decision

Memory is one port with five independent implementations, a composite that runs them, and a
per-session switch for each one.

### The port

Every layer implements `MemorySource`. It has a read half and a write half.

```python
class MemorySource(Protocol):
    id: MemorySystemId

    # read half - runs before the prompt is built
    async def recall(ctx) -> tuple[MemoryFragment, ...]: ...

    # write half - runs after a successful turn
    async def observe(ctx) -> None: ...


@dataclass(frozen=True, slots=True)
class MemoryFragment:
    source: MemorySystemId
    label: str          # "[Story So Far]", "[Lore]"
    body: str
    priority: int       # resolves budget contention
    tokens: int
```

`MemoryPipeline` runs the enabled sources at the same time. It merges the fragments into one
ordered block. It cuts the block to the token budget by `priority`. `ConversationBuilder` renders
that block in place of the hardcoded sentence.

### The five layers

| Layer | Holds | Retrieved by | Extra model work | New infrastructure |
|---|---|---|---|---|
| 00 recent window | the last N turns, word for word | always. It is the history | none | none |
| 01 rolling summary | what the window dropped, compressed | always, as "the story so far" | 1 call every N turns | 1 table |
| 02 lorebook | authored facts that do not change | keyword triggers over recent messages | none | 1 to 2 tables, plus admin create-read-update-delete (CRUD) |
| 03 fact and state store | extracted facts with validity windows | scoped query on the entities in scene | 1 extraction per turn | 2 tables, plus a background worker |
| 04 vector recall | any past message or fact, addressed by meaning | hybrid rank of similarity, keyword and recency | 1 embedding per turn, plus 1 per chunk | pgvector, new database images, a second resident model |

The layers are complements, not alternatives. Each one fails in a way the next one covers. Layer
01 loses exact wording. Layer 02 misses paraphrase. Layer 03 accumulates contradictions. Layer 04
returns text that is similar but not relevant.

### Per-session control

`MemorySettings` is a frozen value object on `ScenarioSession`. It mirrors `SessionDirectives`. It
holds the enabled set and the per-source budgets. The `with_*` methods return new instances.

It rides in the existing session JSONB payload. It gets no new column. It uses the same
degrade-to-default deserialization that keeps old export files loadable.

Layer 00 cannot be switched off. It is the conversation itself, so the rule "every session has at
least one memory system" costs nothing to hold. Layers 01 to 04 are switched per session. Defaults
come from settings. Players control them through a `/memory` command, next to `/rules` and
`/director`. Operators control them from the admin panel.

Under the ADR-025 rule, `MemorySettings` is player-owned state. `/restart` keeps it. `/clear`
resets it to defaults.

### Build order

| Story | Scope |
|---|---|
| S021 | this ADR and the memory design docs. No code. |
| S022 | token counter, layer 00, and the pipeline skeleton |
| S023 | layer 01, the rolling summary |
| S024 | layer 02, the lorebook, with full-text triggers |
| S025 | layer 03, the fact and state store |
| S026 | layer 04, vector recall. Only if a concrete failure demands it. |

### Two decisions this ADR settles once

**Embeddings are deferred, but the port is designed now.** Define an `EmbeddingProvider` port and
put a retrieval source behind it. Ship a Postgres full-text implementation first. Postgres
`tsvector` and `ts_rank` give stemmed, ranked matching for free. That closes most of the
paraphrase gap with no embedding model. If semantic recall turns out to matter, pgvector becomes a
migration and an adapter, not a redesign.

**The background worker shape is decided here, not per epic.** The repository has no job runner.
Layer 01 can summarize on the turn path and accept a visible pause. Layer 03 cannot. Extraction
and consolidation must run off the write path. S021 picks one mechanism, either a task started by
the calling service or a runtime component owned by `app/lifespan.py`. S023 and S025 then use it
instead of each inventing one.

## Alternatives

* **Keep `DumpEverythingStrategy` and raise the context window.** Rejected. It moves the
  overflow point. It does not remove it. Cost per turn grows with the length of the story, and
  the model attends worse to a very long prompt.
* **One memory manager that owns storage, selection, summarization and retrieval.** Rejected.
  ADR-013 rejected it for good reasons that still hold. This design keeps the same separation and
  splits only the strategy half into five parts.
* **Install Mem0, Zep Graphiti or Letta.** Rejected for now. These are good systems. The design
  study reports Graphiti at 63.8% against Mem0 at 49.0% on the LongMemEval benchmark, and the gap
  is almost all temporal reasoning. The mismatch is architectural, not one of quality. Each one
  arrives with its own storage layer, its own model client, and its own opinion about the agent
  loop. That lands either inside a core that must not import a framework, or beside the
  Postgres-only rule of ADR-024. None of them speaks this domain: scenes, characters, lore,
  director instructions. `MemorySource` stays small enough to wrap any of them later as one
  source, in `infrastructure/`, with no change to the core.
* **Build layer 03 or 04 first, because they fix the hardest failures.** Rejected. Both are large.
  Both need infrastructure the repository does not have. Layer 01 is mostly an integration job for
  code that already exists, and it is the fallback the deeper layers need when they return
  nothing.

## Rationale

* The toggle architecture is the expensive part to get wrong and the cheap part to get right on
  paper. Ordering, budget contention and the fragment contract are hard to change once five
  sources depend on them.
* Adding a sixth layer touches no existing source.
* The order follows value per unit of work in this codebase, not depth. Layer 01 has a working
  summarizer waiting. Layer 04 needs two new container images and a second model in video memory.
* Borrow the ideas from the published systems now. Keep the option to borrow the implementation.
  The idea worth taking at once is bi-temporal supersession. Append without loss. Consolidate
  later. Never overwrite. Every serious system has converged on it, and every one still struggles.
  The design study reports consolidation accuracy across evaluated systems between 14% and 60%.

## Consequences

### Positive

* Long sessions stop overflowing the context window, from S022 on.
* Each layer ships and is judged on its own. A bad layer is switched off per session, not removed.
* The two unused JSONB columns get a purpose.
* Scenario authors get a layer they control by hand. A wrong lorebook result is a bug that can be
  pointed at, not a model that drifted.
* Prompt assembly gets one memory block with a stated budget, instead of an unbounded replay.

### Negative

* Five sources plus a pipeline is more code than one strategy class, and more to keep mypy clean.
* Token counting becomes a hard dependency of the prompt path. A wrong counter silently drops
  story.
* The `MemoryStrategy` port is replaced, not extended. It is synchronous. It receives only
  messages, with no session, no scenario and no budget. Four call sites in `ChatService` and one
  line in `app/main.py` change with it.
* Layer 03 will accumulate wrong facts. That is the known failure of every system in this class.
  Build it after layer 01 exists to fall back on.
* Every layer after 00 adds latency or model calls to a turn, or work off the turn path that can
  fail on its own.

### Blocking defect to fix first

`ChatService._build_debug_prompts` slices system messages by position. Slot 0 is read as the
character prompt, slot 1 as the world prompt, slot 2 as the conversation rules. Those indices are
already wrong, because S014 inserted the language, rules and director sections ahead of them. A
memory section shifts them again. Fix this in S022 before the builder changes, not after.

## Supersedes

This ADR supersedes three milestone-scoped rules in ADR-013.

1. "Do not implement summarization, retrieval, embeddings, or hybrid memory logic in this
   milestone." Milestone 2 is over. Layers 01 to 04 implement exactly these.
2. Implementation rule 5, "Milestone 2 strategy must be `DumpEverythingStrategy` only."
3. Implementation rule 1, "Do not create a generic memory manager that combines storage and
   strategy", but only in part. `MemoryPipeline` is a memory manager. It does not combine storage
   and strategy. It composes strategies. It never persists a conversation.

ADR-013's core decision stands. Conversation storage and context building stay separate concerns
behind separate ports. Rules 2, 3 and 4 stand unchanged.

`ARCHITECTURE.md` describes a "Memory Manager" that ADR-013 forbade. S021 updates that document so
the name matches `MemoryPipeline` and the description matches this ADR.

## Implementation Rules

1. Keep persistence out of memory sources. A source that stores its own data does so through a
   port, like every other core component.
2. Every source returns fragments. No source writes to the prompt directly.
3. The pipeline owns the budget. A source reports its token cost. It does not decide whether it
   fits.
4. A source that fails must not fail the turn. Log it, drop its fragments, and continue.
5. Layer 00 is always enabled. The settings type must make this unrepresentable, not merely
   validated.
6. Never delete a fact in layer 03. Stamp `invalid_at` and record what replaced it.
7. Resolve conflicts by subject and predicate slot first. Involve the model only when the
   deterministic rule cannot decide.
8. Embed nothing raw. Layer 04 indexes summaries and extracted facts, which makes layer 03 a
   prerequisite for layer 04 being any good.
