---
id: ADR-027
title: Lorebook Paraphrase Gap - Trigger-Phrase Expansion, Not Embeddings
status: accepted
created: 2026-09-04
supersedes: []
superseded_by: []
---

# ADR-027 — Lorebook Paraphrase Gap - Trigger-Phrase Expansion, Not Embeddings

## Context

ADR-026 already named a known limit of layer 02, the lorebook: "Layer 02 misses paraphrase.
[...] What it misses: paraphrase that shares no stem with any trigger key, and any relation
between words the English stemmer does not treat as the same lexeme." That ADR left the size of
this gap, and what to do about it, for later.

A benchmark (`benchmark/`, a synthetic blacksmith scenario - never real user data) measured it
directly. It ran 60 player messages through the real matching-and-generation pipeline and found
14 of them were clearly on-topic for a lore entry, by a careful human read, but were missed
because they used a metaphor or synonym instead of a listed trigger word - "spun glass" for
"fragile," "old companion" for "old friend," "grip alone seems to rival the mighty anvil" for
"strong" without the word itself appearing.

The benchmark also tested two possible fixes: a prompt-level instruction telling the model to
double check that retrieved lore actually fits before using it, and small-scoped local embedding
search - semantic matching restricted to the handful of lore entries themselves, not full
conversation history (that larger idea is layer 04, already deferred by ADR-026, and out of
scope here).

## Decision

1. Do not adopt the "check relevance before using it" prompt instruction. It showed no
   measurable effect.
2. Do not pursue small-scoped local embedding search as the fix for the paraphrase gap. It was
   tested directly, with real local models, and rejected.
3. Close the gap going forward by manually authoring more trigger-phrase variants per lore entry
   (synonyms and likely metaphors an author anticipates), accepting that this will not catch
   every paraphrase - the same fallback ADR-026 already named as available.

## Alternatives

* **Full layer-04 semantic recall over conversation history.** Out of scope: that layer solves a
  different, larger problem (recalling facts from past conversation), and ADR-026 already defers
  it until a concrete production failure demands it.
* **Small-scoped embeddings over just the lore entries.** Tested directly - see Rationale.
* **LLM-as-relevance-judge** (asking the model directly whether a fact applies, instead of a
  similarity score). Not tested. Left open as a future option if the paraphrase gap turns out to
  matter in real production use.
* **Accept the gap as-is, do nothing.** The implicit fallback if trigger-phrase expansion also
  proves insufficient in practice.

## Rationale

**The prompt instruction showed no effect.** The benchmark compared replies with and without the
instruction across two categories built to catch it - one where retrieved lore could tempt the
model to overshare a private history, one where a bare trigger word fires on unrelated text. A
human read (not just the automated keyword-leak heuristic) found no meaningful difference between
the two conditions in either category. The one case the heuristic flagged turned out to be
ordinary in-character safety talk, not an actual leak of private history, once read in context.
Separately, the test character was written with "reserved" as an explicit personality trait and
every test message was a cold open with no prior conversation, so even a real effect could not
have been cleanly isolated by this test design - the character's default reticence toward a
stranger is a large, uncontrolled confound.

**Embeddings were tested three times and rejected each time.** Three different local models -
`nomic-embed-text-v1.5` (768-dim), `bge-small-en-v1.5` (384-dim), `bge-large-en-v1.5` (1024-dim,
roughly 10x `bge-small`'s parameter count) - were each used to embed the four lore entries and
all 60 test messages, then scored by cosine similarity. Each model:

* Correctly separated the one already-known problem (a bare "strong"/"strength" trigger firing
  on unrelated text) from genuine matches, with no score overlap. This part worked in all three
  runs.
* Failed to reliably separate genuine paraphrase matches from generic-vocabulary false matches
  overall. No single similarity cutoff worked in any of the three runs - the score range for
  "should match nothing" always overlapped the score range for "should match something."
* Recovered some but not all of the 14 paraphrase misses, and a large share of the correct picks
  were wins by a razor-thin margin (sometimes under 0.01 apart from the wrong answer - effectively
  a coin flip): 5 confident / 6 thin / 3 wrong (nomic), 3 confident / 5 thin / 4 wrong
  (`bge-small`), 1 confident / 5 thin / 3 wrong / 5 in an unclassified middle band (`bge-large`).
* Got worse, not better, with scale. The 10x-larger `bge-large` model had the smallest bare-word
  score gap of the three (0.038, versus 0.058 and 0.109), the fewest confident correct answers,
  and introduced a third, unexplained false-match mode (`bge-large` also confused two unrelated
  messages with the character's lost-friendship history) on top of the forge-vocabulary confusion
  `bge-small` already showed. Embedding compute time was never the bottleneck at any of the three
  scales (all three ran in a few seconds), so scale bought nothing there either.

This matches, rather than contradicts, a separate research pass
(`docs/research/2026-09-04-pgvector-at-small-scale.md`) that found this small a lore corpus does
not carry the infrastructure or scale problems the earlier, larger-corpus pgvector evaluation
(`docs/research/2026-09-03-lore-retrieval-keyword-vs-semantic.md`) raised. The corpus-size
objection genuinely does not apply here. What the benchmark found instead is a different problem:
embedding quality itself, at this task, for short lore entries and short player messages, was not
good enough to hang a reliable decision on, in three separate attempts.

**Trigger-phrase expansion is not chosen because it is proven to close the whole gap** - it
plainly will not catch a paraphrase nobody thought to list. It is chosen because it costs nothing
beyond authoring time, needs no new infrastructure, and is the one option in this decision that
was not empirically tried and rejected.

## Consequences

### Positive

* No new infrastructure, dependencies, embedding model, or runtime cost.
* A concrete, actionable practice for lore authors: list two to four trigger phrases per fact
  (synonyms, common rephrasings) instead of one.
* Closes this investigation with real numbers instead of an untested assumption either way -
  three models, three separate scales, one already-known problem confirmed fixable and one
  paraphrase problem confirmed not reliably fixable by this approach at this task.

### Negative

* Will not catch a paraphrase the lore author did not anticipate. The gap is mitigated, not
  solved.
* Depends on ongoing authoring discipline (a human remembering to add synonyms when writing or
  editing a lore entry), not a systemic guarantee.
* If the practical miss rate stays unacceptable after this, the remaining options - an
  LLM-as-relevance-judge, or revisiting layer 04 if a concrete production failure demands it, per
  ADR-026 - have not been ruled out, only deprioritized behind the cheaper fix.
