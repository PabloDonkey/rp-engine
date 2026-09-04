# Keyword vs semantic lore retrieval, at S024's scale

**Question.** ADR-026 (`docs/adr/0026-layered-memory.md`) defers layer 04, semantic recall over
pgvector, "only if a concrete failure demands it." S024 shipped layer 02, the lorebook
(`docs/MEMORY.md`), and found a real failure while testing against the Jane pilot data: two
hand-written trigger keys never fired in second-person play. Does that failure cross the bar? This
document researches the alternatives before answering.

**Scope note.** The corpus this layer serves is small by construction: a handful of hand-authored
entries per scenario (four in the Jane pilot), capped to the top three matches a turn
(`DEFAULT_MATCH_LIMIT` in `src/rp_engine/core/memory/lorebook_source.py`). Every claim below is
read against that scale, not against the thousand- or million-document corpora most retrieval
literature targets.

---

## The two failures, precisely

From `docs/MEMORY.md`'s layer 02 section and the current matching code
(`src/rp_engine/infrastructure/postgres/repositories/lorebook_store.py`,
`PostgresLorebookStore.find_matching`):

```python
recall_vector = func.to_tsvector("english", recall_text)
trigger_query = func.to_tsquery("english", LoreEntryRecord.trigger_query_expr)
rank = func.ts_rank(recall_vector, trigger_query)
```

`trigger_query_expr` is built in `_trigger_query_expr`: each trigger phrase becomes an AND'd group
of its own words, phrases are OR'd together, and non-word characters are stripped. Two Jane-pilot
triggers failed against real second-person play:

1. **`strength` / `strong` do not share a stem.** Postgres's English (Snowball) stemmer treats
   them as unrelated lexemes, so a trigger on one word structurally cannot match text using the
   other. This is a derivational-morphology gap, not a typo.
2. **The player never types the character's name.** A trigger built around `"Jane's strength"`
   cannot fire in a conversation where the player addresses her as "you." Resolving `{{char}}`
   inside trigger text — the fix that works for fragment *bodies* — would not help, because the
   template resolves to `Jane`, and `Jane` is exactly the word the player never types.

---

## 1. Is there a well-known middle ground between full-text search and full embedding RAG?

Yes, several, but they solve different problems, and only one of them is free.

**pg_trgm (character trigram similarity).** Official Postgres documentation
([`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html)) describes `similarity()`,
`word_similarity()`, and the `%` operator as trigram-overlap measures over three-character windows,
with GiST/GIN index support. The docs' own worked example for combining `pg_trgm` with full-text
search is spell-correction: build a word list from `ts_stat`, then use `similarity(word,
'misspelled_word')` to suggest corrections. That is the mechanism's real target — character-level
noise, i.e. typos. It is not built for derivational pairs like `strength`/`strong`, which barely
overlap as trigrams (`strength` → `str`, `tre`, `ren`, `eng`, `ngt`, `gth`; `strong` → `str`, `tro`,
`ron`, `ong` — one shared trigram out of ten). `pg_trgm` would not have closed either S024 gap.

**Postgres synonym/thesaurus dictionaries.** Official documentation
([§12.6, Dictionaries](https://www.postgresql.org/docs/current/textsearch-dictionaries.html)) is
explicit: both dictionary types are configured with `CREATE TEXT SEARCH DICTIONARY ... (TEMPLATE =
synonym, SYNONYMS = my_synonyms)` — but the `SYNONYMS`/`DictFile` parameter names a `.syn`/`.ths`
file that must exist under `$SHAREDIR/tsearch_data/` on the server. SQL alone cannot define the
mapping. That means a synonym table for `strength ↔ strong` costs a custom Postgres image — smaller
than pgvector's, since it needs no new extension and no second model, but the same *class* of cost
ADR-026 is trying to avoid: a non-default image, for both `docker-compose` and the testcontainers
fixture.

**An application-side word-family table.** The cheap alternative: expand known non-cognate word
pairs in Python, inside `_trigger_query_expr`, before the expression reaches Postgres at all. This
needs no new infrastructure — it is a code change in a function that already tokenizes trigger
text. This is the "small synonym/thesaurus expansion table" the research brief asks about, just
placed on the side of the stack that doesn't require a new container image.

**Hybrid BM25 + embeddings.** Anthropic's
[Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) engineering post
reports that combining contextual embeddings with contextual BM25 cut the top-20-chunk retrieval
failure rate from 5.7% to 2.9% (a 49% reduction), and reranking on top of that cut it to 1.9% (67%
total). These are real, published numbers — but they come from a corpus of "many thousands" of
document chunks in a general-purpose knowledge base, the regime hybrid retrieval is built for. They
say nothing about whether hybrid search beats pure keyword matching over four documents.

**How a peer system in the same genre actually solves this.** SillyTavern's World Info — the
closest thing to a prior art "lorebook" for text role-play — matches primary keys against chat
text, with **secondary keys** as an optional AND/OR/NOT filter, **whole-word matching** enabled by
default, and a per-entry **`constant`** flag that makes an entry always-on regardless of keyword
match at all
([SillyTavern World Info docs](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)). It
also ships an *optional* embedding-based activation path through its Vector Storage extension, for
entries explicitly flagged "vectorized" — but its own docs caution that "the retrieval quality
depends entirely on the outputs of the embedding model, it's impossible to predict exactly what
entries will be inserted." SillyTavern's design keeps keyword matching as the default and treats
embeddings as an opt-in escape hatch for a minority of entries, not the baseline. Nothing in its
documentation describes special handling for second-person address or pronouns; that gap is left to
the author, same as this codebase's `{{char}}` convention leaves naming to the author.

**Conclusion for Q1:** the real middle ground for this scale is authoring convention plus a small
Python-side word-family table — not `pg_trgm` (wrong problem: spelling, not morphology) and not a
Postgres synonym dictionary (right problem, wrong cost: it needs the same kind of custom image
ADR-026 is deferring pgvector to avoid).

---

## 2. At tens-to-low-hundreds of entries, does semantic search empirically beat full-text search enough to justify pgvector?

The retrieval literature's headline results are almost all measured at a scale several orders of
magnitude larger than this layer will ever hold, and where they do speak to corpus size, the trend
runs the wrong way for embeddings.

**Dense retrieval degrades as unrelated candidates accumulate; BM25 does not.**
["Beyond the Needle's Illusion"](https://arxiv.org/pdf/2601.20276) (Lin et al.) evaluates evidence
access as corpus size scales from 64K tokens to 326M tokens and reports a strong dense retriever
(a top embedding model) dropping from SR@10 ≈ 0.93 at 64K tokens to ≈ 0.68 at 326M tokens, while
lexical retrieval stays comparatively robust as scale increases. The mechanism the paper gives:
larger corpora add more near-miss "semantic interference" — text that embeds close to the query
without being the right answer. A four-entry lorebook has almost no room for that failure mode to
occur: there are only three other candidates a wrong match could be confused with.

**BM25's relative strength grows, not shrinks, as more documents arrive.**
["From BM25 to Corrective RAG"](https://arxiv.org/pdf/2604.01733), tested on a 7,318-document
financial corpus, found BM25 outperforming dense retrieval on every metric except Recall@20, citing
the value of exact terminology matching. The paper does not test small corpora directly, and says
so explicitly, but the direction of its finding — lexical precision matters most where exact terms
carry the meaning — is exactly the situation hand-authored trigger keys are designed to exploit: an
author who knows the target vocabulary can put it directly in `trigger_keys`, something a general
embedding model has to infer from vaguer semantic proximity.

**Hybrid fusion's edge is a function of query variety a four-entry lorebook barely has.** The same
survey (from the earlier search pass on this literature) notes hybrid BM25/dense fusion beats either
method alone, with the largest gains at small *k* — but that gain comes from covering diverse query
phrasings across a corpus large enough that lexical and semantic signals disagree often. With three
slots to fill from four candidates, there is very little space for the two signals to usefully
disagree.

**No benchmark tests this exact regime, and that absence is itself informative.** Every source
surveyed here — BEIR-style suites, Anthropic's Contextual Retrieval post, the scaling papers above —
targets corpora from thousands to hundreds of millions of tokens. None evaluates four-to-fifty
hand-authored short entries. The retrieval-quality argument for embeddings (better recall on
paraphrase, better handling of large candidate pools) is an argument that gets stronger as the
corpus grows and the query vocabulary diversifies. Neither condition holds for a per-scenario
lorebook. The absence of small-corpus benchmarks is not a data gap this document can fill by
extrapolation alone, but every study that varies corpus size points the same direction: embeddings'
edge over lexical matching shrinks, not grows, toward this end of the scale.

**Conclusion for Q2:** no. At this scale, the published evidence does not support that vector search
would meaningfully outperform full-text search on the two observed failures — one is a morphology
gap, the other a referential gap, and neither is the kind of large-candidate-pool ambiguity semantic
search exists to resolve.

---

## 3. Does the second-person / name-mismatch problem have a cheap fix that doesn't need embeddings?

Yes — and the obvious cheap fix that is *not* the answer is worth ruling out precisely, because it
is the first thing anyone reaches for.

**The "always include a second-person alias" idea cannot work as stated, and this is verifiable,
not speculative.** Postgres's default `english` full-text configuration treats common pronouns as
stop words. Reading the actual stopword file shipped with the Postgres 16 install on this machine
(`/usr/share/postgresql/16/tsearch_data/english.stop` — the same major version this repo's
docker-compose and testcontainers fixture target) confirms it directly:

```
$ grep -E "^(you|your|yours|she|her|he|him|his)$" /usr/share/postgresql/16/tsearch_data/english.stop
you
your
yours
he
him
his
she
her
```

Postgres's own documentation confirms what that means for a query built from only such words. The
[`numnode()` function reference](https://www.postgresql.org/docs/current/textsearch-features.html)
gives this exact worked example:

```
SELECT numnode(plainto_tsquery('the any'));
NOTICE:  query contains only stopword(s) or doesn't contain lexeme(s), ignored
 numnode
---------
       0
```

A trigger key of `"you"` or `"your character"` would reduce to an empty `tsquery` at query time —
`to_tsquery('english', LoreEntryRecord.trigger_query_expr)` in `PostgresLorebookStore.find_matching`
— which matches nothing, silently, with only a server-side NOTICE nobody sees on this code path. So
"add an implicit second-person alias to every entry" is not merely a weak idea; under the current
`english` configuration it is a no-op. Any fix along these lines would first have to work around the
stopword list — for example by using the `simple` configuration for an alias-only sub-check, which
throws away stemming for that path — before it could even be tested.

**The fix that actually works, and is already shipped, is authoring against the topic, not the
entity.** `docs/MEMORY.md`'s own account of S024 states the working conclusion: "Write triggers as
the words a player would actually type, not as a paraphrase of the concept." The archived session
notes (`.devloop/archive/S024-2026-09-03-lorebook.md`) confirm this was not left as a
recommendation — it was applied and verified: "triggers rewritten after real-data testing surfaced
that the handoff document's literal trigger phrasing did not fire in practice," followed by 14 of 14
hand-run example messages retrieving the expected entry (or correctly nothing) once the triggers
were rewritten. The failure was not "second-person address defeats keyword matching in general." It
was "a trigger keyed on the character's name and an abstract trait-word defeats keyword matching,"
and the fix — trigger on the situational vocabulary a player uses when the topic comes up, e.g. the
concrete nouns and verbs of the scene, not the character's name or a document's descriptive prose —
sidesteps the referential gap entirely: a player describing a scene's content doesn't need to name
the character to trigger lore about it, because the trigger no longer depends on the name.

**This lines up with how the closest peer system handles the same class of problem.** SillyTavern's
World Info has no documented second-person-aware or pronoun-aware matching either (confirmed by
reading its docs directly). Its tool for widening a trigger's reach is secondary keys and
`constant` (always-on, no keyword needed) entries — i.e., the author decides when an entry should
fire independent of exact wording, the same authoring-level lever this codebase already has.

**Conclusion for Q3:** yes, there is a cheap fix, and it does not need embeddings — but it also does
not need new code. It is the authoring convention `docs/MEMORY.md` already states and S024 already
applied: trigger on concrete scene vocabulary, not on the entity's name or an abstract paraphrase.
The one thing worth ruling out explicitly, because it looks cheap and is not, is baking an implicit
pronoun alias into every entry — Postgres's stopword list makes that a silent no-op, not a partial
fix.

---

## 4. Does the ADR's layer-04-after-layer-03 ordering hold up?

ADR-026's Implementation Rule 8 states it precisely: "Embed nothing raw. Layer 04 indexes summaries
and extracted facts, which makes layer 03 a prerequisite for layer 04 being any good." This is a
narrower claim than "layer 04 cannot exist before layer 03 for any purpose" — it is a claim about
*what layer 04, as ADR-026 defines it, is for*: recall over "any past message or fact, addressed by
meaning" (the ADR's layer table). That scope is a semantic index over the conversation's history and
its extracted state — exactly the kind of unstructured, verbose, redundant text that embeds badly
raw. Anthropic's Contextual Retrieval post makes the same point from the other direction: its whole
technique is manufacturing a compact, situating summary for each raw chunk *before* embedding it,
because embedding raw chunks performs worse. ADR-026's rule 8 is the same finding, arrived at
independently: don't embed the noisy version when a clean, compact version is available or
buildable. That argument holds, and nothing surveyed here weakens it.

**Could layer 04 index lore entries instead, without waiting for layer 03?** Technically yes, and
without violating rule 8's actual spirit: `LoreEntry.content` is already short, hand-authored,
curated text — structurally closer to an "extracted fact" than to a raw chat turn. Embedding four
curated paragraphs is not the abuse rule 8 warns against.

But this would not be "layer 04" in ADR-026's sense, and it would not fix the observed failure. Two
reasons:

1. **Layer 04's scope in the ADR is recall over history and facts, not a semantic replacement for
   layer 02.** An embedding index over lore entries would be a variant *of layer 02* — a semantic
   fallback for lorebook matching — not the vector-recall layer ADR-026 reserved id 04 for, which
   is meant to complement layers 01 and 03, not compete with layer 02's own retrieval. Building it
   would not close the "ship layer 04" story in the ADR's build order; it would open a different,
   smaller, unplanned one.
2. **The cost is paid on the query side regardless of what's indexed.** Even a perfect embedding
   index over four lore entries still needs the player's raw second-person message embedded, every
   turn, to query it — the exact "one embedding call per turn" cost ADR-026 already prices for
   layer 04, for a corpus where keyword matching, once triggers are authored correctly, already
   scores 14 for 14 against real hand-run test cases.

**Conclusion for Q4:** the ordering logic holds for what layer 04 is actually scoped to do. It does
not forbid a narrower, hypothetical "semantic lorebook" as a variant of layer 02 — but that variant
is a different feature than the one the ADR reserved layer 04 for, and nothing in this research
shows it would fix a failure that authoring discipline hasn't already fixed for free.

---

## Recommendation

**S024's real-world experience does not cross ADR-026's "concrete failure demands it" bar. Layer 02
stays sufficient, and the fix is cheaper than anything requiring new infrastructure.**

The two observed failures are not evidence that keyword matching is the wrong retrieval strategy for
this corpus. They are evidence that the pilot's first-draft triggers were authored wrong — copied
from a design document's descriptive prose instead of the vocabulary a player actually types — and
that mistake was already caught and already fixed within S024 itself, verified against 14 of 14
hand-run real messages. Nothing about that failure scales with corpus size, paraphrase diversity, or
candidate-pool ambiguity — the three things embeddings are good at fixing, and the three things the
surveyed literature agrees embeddings need a large, varied corpus to pay for. A four-to-fifty-entry,
hand-authored, top-3-per-turn lorebook is close to the worst-case corpus for justifying pgvector's
cost: a new Postgres image for two environments, a second resident model, and a per-turn embedding
call, to solve a problem that an authoring convention already solved for nothing.

**Concrete shape, in priority order:**

1. **Keep and formalize the authoring convention already in `docs/MEMORY.md`.** Trigger on the
   concrete scene vocabulary a player would type — actions, objects, situational nouns — never on
   the entity's literal name alone and never on an abstract paraphrase lifted from prose. This is
   not a proposal; it is what S024 already shipped and verified. Nothing here asks for new code.
2. **For the specific stemming gap (case 1, `strength`/`strong`), let authors list multiple trigger
   phrases covering each word form**, using the schema exactly as it exists today —
   `trigger_keys=("Jane is strong", "Jane's strength", ...)` are already OR'd together by
   `_trigger_query_expr`. This costs zero new code and zero new infrastructure, and is strictly
   cheaper than either a Postgres synonym dictionary (needs a custom image, per §1's finding) or a
   Python-side word-family table (needs code, a maintained mapping, and test coverage, for a
   problem three OR'd trigger phrases already solve per entry).
3. **Do not add `pg_trgm`.** It is a character-similarity tool for typos. Neither observed failure
   is a spelling problem, and `strength`/`strong` share too few trigrams for `pg_trgm` to help even
   incidentally.
4. **Do not add a Postgres-side synonym or thesaurus dictionary.** It solves case 1 correctly but at
   the cost of a custom Postgres image for both `docker-compose` and the testcontainers fixture —
   the same class of infrastructure tax ADR-026 defers pgvector specifically to avoid, for a problem
   already solved by trigger-authoring at zero cost.
5. **Do not build layer 04 now.** ADR-026's own ordering rule — embed facts and summaries, not raw
   text — is correct and independently corroborated by Anthropic's Contextual Retrieval findings.
   Layer 03 is a real prerequisite for layer 04 being worth its cost, not an arbitrary sequencing
   choice. Revisit only if a *future* failure survives good-faith trigger authoring — this one did
   not survive it.
