# pgvector at lorebook scale: does the prior "too small to justify" verdict still hold?

**Question.** `docs/research/2026-09-03-lore-retrieval-keyword-vs-semantic.md` (hereafter "the
09-03 doc") rejected full pgvector-based semantic search over the whole memory system, citing
evidence that dense retrieval degrades as the *overall corpus* grows, and concluding that a
four-to-fifty-entry lorebook is "close to the worst-case corpus for justifying pgvector's cost."
A new prototype (`scripts/prototype_lore_relevance_check_results.jsonl`, in the uncommitted
worktree at `.claude/worktrees/lore-relevance-prototype`) found a concrete gap the 09-03 doc did
not test: metaphor and synonym paraphrase. Does the 09-03 doc's small-corpus argument still hold
when the corpus in question is not "the whole memory system" but a single, deliberately tiny,
bounded set — the lore entries themselves? This document researches that narrower question. It
does not revisit anything the 09-03 doc already settled (pg_trgm, Postgres synonym dictionaries,
the stemming/second-person gaps, ADR-026's layer-04 ordering).

**Scope note.** This is not a proposal to build layer 04. ADR-026 (`docs/adr/0026-layered-memory.md`)
scopes layer 04 as semantic recall over conversation history and extracted facts — a different,
larger corpus than lore entries. What follows evaluates a narrower, hypothetical variant of layer
02 itself: embeddings computed only over the lorebook's own short, hand-authored entries. The
09-03 doc already flagged this as a live possibility without researching it (§4: "Could layer 04
index lore entries instead... Technically yes... `LoreEntry.content` is already short,
hand-authored, curated text").

**The confirmed gap.** Reading `scripts/prototype_lore_relevance_check_results.jsonl` directly:
across the four categories where a lore entry should fire (`true_positive`, `contradiction`,
`near_miss`, `dont_invent`), the baseline keyword matcher missed 14 of 40 generated messages.
Two examples, verbatim from the results file:

- `"Reya, you move those sparks like they're spun glass; are you always so cautious because you
  dread actually damaging anything?"` — no trigger key match. The lore entry's trigger keys are
  `["strength", "strong", "careful", "gentle", "fragile", "restraint"]`; "spun glass" shares no
  word, and no stem, with any of them.
- `"I sometimes wonder if you ever think of your old companion, and if you've ever considered
  reaching across that distance..."` — no trigger key match. The trigger keys are `["betrayal",
  "old friend", "trust", "abandoned", "friendship"]`; "companion" and "friend" are unrelated
  lexemes to Postgres's stemmer, the same class of gap as `strength`/`strong` in the 09-03 doc,
  except here there is no shared root at all — `pg_trgm` would fare even worse than it did on
  `strength`/`strong` (§1 of the 09-03 doc already ruled it out for exactly this reason: trigram
  overlap requires shared substrings, and `companion`/`friend` share none).

---

## 1. At tens-to-low-hundreds of vectors, does an index even help, or is exact search enough?

**pgvector's own documentation says exact search is the default, with perfect recall, and stays
competitive at small scale.** The [pgvector README](https://github.com/pgvector/pgvector) states
plainly: "By default, pgvector performs exact nearest neighbor search, which provides perfect
recall." Approximate indexes (HNSW, IVFFlat) exist specifically to trade that perfect recall away
for speed at larger scale — the README's own framing is "unlike typical indexes, you will see
different results for queries after adding an approximate index." Its Troubleshooting section
addresses small tables directly: "Also, if the table is small, a table scan may be faster." No
threshold number is given, but the direction is unambiguous — at small N, the exact-search default
is not just correct, it is expected to be the faster choice too, and adding an approximate index
is something you would have to justify, not something the docs recommend by default.

**IVFFlat's own instructions assume a much larger N than this project will ever have.** The
[README's IVFFlat section](https://github.com/pgvector/pgvector) says to "create the index _after_
the table has some data" (it trains on a sample) and gives its `lists` parameter formula as "`rows
/ 1000` for up to 1M rows and `sqrt(rows)` for over 1M rows." At `rows / 1000`, a lorebook of 100
to 300 entries computes to `lists = 0`, i.e. the formula's own arithmetic is undefined at this
scale — a direct signal that IVFFlat is not designed with a corpus this size in mind. HNSW has no
equivalent training step, but its parameters (`m` — "the max number of connections per layer (16
by default)", `ef_construction` — "the size of the dynamic candidate list for constructing the
graph (64 by default)") govern a graph-navigation structure whose entire value proposition is
avoiding an exhaustive scan over a *large* candidate set. Neither index type's documentation
describes a benefit at a scale where the exhaustive scan itself is already cheap.

**A second primary source agrees, independently.** The official
[sentence-transformers semantic-search documentation](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)
states: "For small corpora (up to about 1 million entries), we can perform semantic search with a
manual implementation" — i.e., brute-force cosine similarity, no ANN library, no index tuning. A
lorebook of dozens to low hundreds of entries sits four to five orders of magnitude below the
scale at which this independent, widely-used reference implementation says an index becomes worth
adding at all.

**Conclusion for Q1:** no index is needed, and none should be added. At this scale, pgvector's
default exact search already gives perfect recall (by pgvector's own definition of the term) with
no recall/speed tradeoff to manage, no index-build step, and no `lists`/`m`/`ef_construction`
tuning. This removes an entire axis of operational complexity the 09-03 doc was right to weigh
against pgvector for a *larger* corpus — but that axis does not exist at this one.

---

## 2. What would this actually cost, on the stack this project already runs?

**Extension install is a real, concrete change to two files this repo already has.**
`docker-compose.yml`'s `postgres` service currently runs plain `image: postgres:17`.
`tests/conftest.py` starts `PostgresContainer("postgres:16-alpine")` — neither image ships
pgvector. The [pgvector README's installation section](https://github.com/pgvector/pgvector)
gives two paths: an official Docker image, `docker pull pgvector/pgvector:pg17-bookworm` (tags run
from `pg13` up), or `sudo apt install postgresql-17-pgvector` on Debian/Ubuntu inside a custom
image. Either way, `docker-compose.yml`'s base image changes. The testcontainers fixture is the
sharper problem: pgvector's official Docker Hub tags are Debian-based only (`bookworm`/`trixie`) —
there is no official Alpine tag. Swapping `postgres:16-alpine` for pgvector support means either
moving the test fixture off Alpine to a heavier Debian-based image (slower container pulls/starts
for a fixture `tests/conftest.py` already spins up fresh per test session, per this repo's
`CLAUDE.md`), or depending on an unofficial third-party Alpine build of pgvector — a supply-chain
and maintenance question a solo maintainer should weigh consciously, not inherit by accident. This
is the same *class* of cost the 09-03 doc already priced for a Postgres synonym dictionary (§1:
"a custom Postgres image... for both `docker-compose` and the testcontainers fixture") — real, but
bounded to image selection and one Alembic migration, not a new service.

**The Python side needs no new database driver or ORM pattern.** This project's `pyproject.toml`
already pins `sqlalchemy[asyncio]>=2.0.43` and `asyncpg>=0.30.0`. The
[pgvector-python README](https://github.com/pgvector/pgvector-python) states it "Supports Django,
SQLAlchemy, SQLModel, Psycopg 3, Psycopg 2, asyncpg, pg8000, and Peewee" and shows the query as
`session.scalars(select(Item).order_by(Item.embedding.cosine_distance([3, 1, 2])).limit(5))` — a
normal SQLAlchemy `order_by` clause, not a different querying model from what
`PostgresLorebookStore.find_matching` already does. One new dependency, one Alembic migration
(consistent with this repo's own rule: "PG schema changes require an Alembic migration that is
reversible").

**Embeddings can be computed locally through the LM Studio dependency this project already has,
with no external API.** `pyproject.toml` already pins `lmstudio>=1.5.0`, used today in
`src/rp_engine/infrastructure/llm/lmstudio/` for chat completion and (per ADR-026's token-counter
decision) token counting via a call to the local LM Studio server. LM Studio's own docs
([Embeddings](https://lmstudio.ai/docs/developer/openai-compat/embeddings),
[Python SDK embedding](https://lmstudio.ai/docs/python/embedding)) show the same local-server
pattern extends to embeddings: an OpenAI-compatible `POST /v1/embeddings` endpoint, and a Python
SDK call of the shape `model = lms.embedding_model("nomic-embed-text-v1.5"); embedding =
model.embed("Hello, world!")`. This is a distinct model handle from the chat-completion model —
meaning it is, concretely, the "second resident model" cost ADR-026 already priced into layer 04's
row of its layer table ("pgvector, new database images, a second resident model"). That cost is
real, but it is not a new *kind* of cost for this project — it is the same "ask LM Studio, run it
locally, cache what doesn't change" pattern ADR-026 already chose for token counting, applied to a
second, smaller, purpose-built model instead of the chat model already loaded.

**Storage cost is trivial, computed directly from pgvector's own formula.** The README states:
"Each vector takes `4 * dimensions + 8` bytes of storage." At a typical embedding-model dimension
(nomic-embed-text-v1.5 uses 768), that is `4*768+8 = 3,080` bytes — about 3 KB — per lore entry.
Even at 300 entries, the entire embedding column costs under 1 MB. This is not a meaningful
storage decision at this project's scale, regardless of which embedding model is chosen.

**Latency has two components, and only one of them is answerable from documentation alone.**
Comparing a query vector against 100–300 stored vectors of a few hundred dimensions each, by exact
search, is a few hundred floating-point dot products — a cost too small to be the bottleneck of a
Telegram turn, and this follows directly from the storage math above (a full table scan reads well
under 1 MB). The dominant added cost is not the vector comparison; it is the one embedding call
per turn needed to embed the player's incoming message before the comparison can run — the same
"one embedding call per turn" line item ADR-026 already priced for layer 04. **This document
cannot state a millisecond figure for that call without fabricating one** — it depends on which
embedding model is loaded and this machine's hardware, and is exactly the kind of number a short
local script (load a small embedding model in LM Studio, time `model.embed()` on a handful of real
player-length messages) would answer directly and cheaply, faster than any citation could.

**Conclusion for Q2:** every piece of this is a bounded, one-time cost on infrastructure this
project already runs — a Postgres image swap plus one migration, one new pinned dependency with a
driver this project already uses, and a second, small, local model loaded into the LM Studio
process that already serves this project's chat completions. Nothing here requires a hosted
embedding API, a new service, or a new class of infrastructure. The one number worth measuring
before committing to this is per-turn embedding latency, and it needs a local timing test, not a
citation.

---

## 3. Is there credible guidance on where dense retrieval starts being unreliable — and is a lorebook nowhere near it?

**The paper the 09-03 doc already cites doesn't measure a corpus this small — and that absence
cuts in this project's favor, not against it.** Reading
["Beyond the Needle's Illusion"](https://arxiv.org/pdf/2601.20276) (Lin et al.) directly (not
relying on the 09-03 doc's summary of it): its own abstract states the study uses "a reference
corpus ladder, ranging from eight domain-isolated 64K-token corpora to a 326M-token MemoryBank."
Sixty-four thousand tokens is already far above the size of this project's lorebook — "dozens to
low hundreds" of entries at roughly 75–150 tokens each (reading actual entry lengths in
`scripts/prototype_lore_relevance_fixture.py`'s `LORE_ENTRIES`, e.g. the ~85-word "The Incident"
entry) totals on the order of 5,000–30,000 tokens, below the paper's *smallest* measured point.
The paper's own stated mechanism for degradation is explicit: dense retrieval's failure mode comes
from "near-miss" documents — ones "semantically close to the gold evidence" that "create dense
interference throughout the context" as the candidate pool grows. A lorebook capped at low hundreds
of entries, with only three slots returned per turn
(`DEFAULT_MATCH_LIMIT`, per the 09-03 doc's own citation of
`src/rp_engine/core/memory/lorebook_source.py`), has very little room for that interference
mechanism to operate — there are only ever a few dozen to a few hundred other candidates a wrong
match could be confused with, not the "hundreds of millions of tokens" regime the paper studies.
**This is not license to extrapolate the paper's trend line below its measured range and claim
dense retrieval would score even higher there — the paper makes no such claim, and this document
does not either.** What it does establish, directly from the primary source, is that no evidence
this project's own prior research relied on actually covers this scale, in either direction.

**Independent, primary-source guidance exists for where small-N stops being "small."**
[sentence-transformers's semantic-search docs](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html),
already quoted in §1, put brute-force semantic search's comfortable range at "up to about 1 million
entries." A lorebook is four to five orders of magnitude below that boundary. Between "a few
hundred entries" and "the point where retrieval literature's degradation findings start to apply"
there is a wide, empty middle this project sits entirely inside.

**Short text is not, on its own evidence, a distinct failure mode for embedding quality —
though it is a real caveat on what "quality" means.** Reading the
[MTEB paper](https://arxiv.org/abs/2210.07316) (Muennighoff et al.) directly: MTEB's own STS
(semantic textual similarity) task is specifically built from sentence-pair datasets — the exact
shape of "does this short phrase mean the same as that short phrase," which is what "spun
glass" ≈ "fragile" or "old companion" ≈ "old friend" actually is. Embedding models are commonly
trained and evaluated on exactly this. But the same paper delivers a real caution directly on
point for question 4 below: "STS is known to poorly correlate with other real-world use cases,"
and the paper's own results section names a specific case — "SimCSE's... low performance on
clustering and retrieval despite its strong performance on STS." A model can score well at "these
two short phrases mean similar things" and still not reliably rank the *correct* lore entry above
other candidates in a retrieval query — those are related but measurably different skills.

**Conclusion for Q3:** nothing surveyed suggests dozens-to-low-hundreds of short entries sit
anywhere near a known unreliability threshold for dense retrieval — the nearest primary-source
boundary found (sentence-transformers' "up to about 1 million entries" for brute-force search) is
orders of magnitude above this scale, and the paper documenting *degradation* at scale starts its
own measurements above this scale too. The one real, source-backed caveat is not about corpus
size at all: STS-style paraphrase quality and retrieval-ranking quality are shown, in the primary
MTEB study, to be different skills that do not automatically transfer — which matters directly for
question 4.

---

## 4. Would this actually close the metaphor/synonym gap the prototype found — or is that a separate problem small scope doesn't fix?

**The specific gap is a strong match for what embedding similarity is built to catch, and a
mismatch full-text search is structurally unable to catch at all.** `pg_trgm` needs shared
character substrings (ruled out in the 09-03 doc for `strength`/`strong`; even weaker here —
"companion" and "friend" share none). Postgres's stemmer only merges shared word roots, which is
why an application-side "word-family table" was the 09-03 doc's recommended cheap fix for
`strength`/`strong` — but that approach is a finite table of known non-cognate pairs an author
enumerates by hand. Metaphor is not enumerable the same way: "spun glass," for "handle carefully /
fragile," is one of an open-ended number of ways a player or a model might phrase the same idea,
and the whole point of a semantic-embedding model — as opposed to a synonym table — is that it
generalizes across paraphrases nobody wrote down in advance, which is exactly what a fixed
word-family list cannot do.

**But the MTEB finding from §3 is the direct answer to whether this is guaranteed to work, and the
honest answer is: not guaranteed, only plausible.** A model can be excellent at "do these two
phrases mean the same thing" (STS) without being equally good at "out of these three-to-five
specific candidate lore entries, is this the right one to retrieve" (retrieval) — the MTEB paper's
own words, quoted in §3, are that these "poorly correlate." The prototype's actual failures are a
retrieval-ranking problem, not an abstract similarity-judgment problem: the question isn't whether
an embedding model *can* recognize "spun glass" and "fragile" as related (STS-style benchmarks
suggest most modern embedding models can), it's whether, ranked against this specific lorebook's
four-to-a-few-hundred *other* entries, the right one comes out on top. Nothing surveyed here — not
pgvector's docs, not sentence-transformers' docs, not the MTEB paper, not the Lin et al. paper —
actually measures that exact question for this exact shape of corpus and this exact class of
paraphrase (open-ended metaphor, not lexical synonymy).

**There is a further specific risk this document cannot rule out from documentation alone.**
Metaphor is a harder case than the synonym pairs STS benchmarks are mostly built from. STS
datasets like STS-Benchmark are built largely from real-world sentence pairs (news, forum posts,
image captions) rescored for similarity — they contain paraphrase and some figurative language, but
this document found no primary source specifically benchmarking creative, in-context metaphor
("spun glass" for "fragile," coined by an LLM inside a specific roleplay scene) as its own category,
separate from ordinary lexical paraphrase. Whether a small local embedding model available through
LM Studio handles *this specific style of metaphor*, generated by *this project's own local LLM in
character voice*, is not something any source surveyed here answers — it is a claim only a local
test against real lorebook entries and real generated messages (the same `scripts/prototype_*.py`
harness already built) can confirm.

**Conclusion for Q4:** semantic embedding search is a structurally better fit for this gap than
any full-text-search variant (confirmed) and a plausible fix (STS-style evidence that embedding
models generally do capture short-phrase paraphrase and synonymy). It is not a proven fix for this
exact gap (the STS/retrieval correlation gap, and the absence of any source testing in-scene
metaphor specifically, are real, named uncertainties, not hedging without a source) — but the tool
to make it a proven fix already exists in this repo: rerun
`scripts/prototype_lore_relevance_check.py`'s 14 known-miss messages, or a small variant of it,
with embedding-based retrieval swapped in for `PostgresLorebookStore.find_matching`, and read the
hit rate directly, before deciding anything at production scope.

---

## Answer

**The 09-03 doc's "too small to justify pgvector" verdict does not carry over to this narrower
question, and it was never meant to — it evaluated a different, larger corpus.** At the scale of
the lorebook itself (dozens to low hundreds of short entries), every cost that made pgvector look
disproportionate for the *whole memory system* either shrinks to near-zero or disappears outright:
no index to choose or tune (§1 — exact search is the documented default and is expected to be
fast enough on its own), storage measured in kilobytes (§2), and no new class of infrastructure
beyond what this project already runs — Postgres plus a local LM Studio process (§2). The
09-03 doc's own literature, read at the source rather than assumed, does not cover a corpus this
small either, in either direction (§3) — there is no evidence this scale is where dense retrieval
struggles, and no evidence it is where dense retrieval shines. What the sources do show clearly is
that STS-style paraphrase competence and retrieval-ranking competence are measurably different
skills (§3, §4) — so "an embedding model can tell these two phrases are similar" is not the same
claim as "an embedding model will retrieve the right lore entry."

**Plain answer: a small, scoped, lore-only embedding index is proportionate to build and is not
disqualified by anything the 09-03 doc's own cited research actually says at this scale.** It is
the cheapest infrastructure add this project has faced for a memory layer so far — one dependency,
one migration, one small local model, no hosted API — and it targets exactly the class of failure
(open-ended paraphrase, not enumerable synonym pairs) that the 09-03 doc's cheap fixes (trigger
rephrasing, an application-side word-family table) cannot fully close, because that fix requires
enumerating every metaphor an author or a player might use, and embeddings exist specifically to
avoid needing that list.

**What remains uncertain, and what a small local test would settle, cheaply, before any of this is
built for real:**

1. **Whether it actually closes the 14 observed misses.** This is answerable directly and cheaply:
   point the existing `scripts/prototype_lore_relevance_check.py` harness at an embedding-based
   match instead of `PostgresLorebookStore.find_matching`, using the same synthetic Reya fixture
   and the same 60 generated messages, and read off the hit rate on the 14 known misses. This is
   the single highest-value next step, and it needs no production code change to run.
2. **Per-turn embedding latency on this machine, with a real local model.** §2 gives the storage
   and comparison-cost math from primary sources but explicitly could not source a millisecond
   figure for the LM Studio embedding call itself — that is a five-minute local timing script, not
   a research question.
3. **Whether an embedding model reliably separates the four to five *other* entries in a real
   lorebook, not just recognizes that a metaphor is "on topic" in the abstract.** §4's MTEB-sourced
   caution (STS quality does not guarantee retrieval quality) means the right test is retrieval
   accuracy against this project's actual candidate set, not a similarity score in isolation.
4. **Whether pgvector's official images are worth adopting over an unofficial Alpine build for the
   test fixture, or whether the fixture should just move off Alpine.** This is a small, concrete
   decision (§2) with no research left to do — it is a preference call once the rest of this is
   judged worth building at all.

This document does not recommend building this. That decision, including whether the local test in
point 1 is worth running before committing further, is the user's to make.
