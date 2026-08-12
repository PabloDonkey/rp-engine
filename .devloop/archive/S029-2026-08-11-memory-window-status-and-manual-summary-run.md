> 🗄️ **ARCHIVED — COMPLETED 2026-08-11.** Frozen; do not edit. Kept as evolution history.
> **Result:** the admin panel now shows where a session stands against the fold line, and an
> operator can run the rolling-summary pass by hand instead of waiting for the next turn. The
> session page gained two status bars, the numbers behind them, and a **Run summary now**
> button. The recap itself is easier to read, in its own framed block.
> **The live run found two real problems, and both are fixed here.** The first gauge measured the
> window against the fold line, which sits at full forever once a story passes it, because folding
> a turn does not delete it. The second was in the engine, not the panel: past the fold line every
> new turn pushed one more turn past it, so the worker called the model on nearly every turn.
> Layer 01 now folds in **batches** (`RP_ENGINE_MEMORY_SUMMARY_MIN_FOLD_SHARE`, 10% of the
> budget), and the panel shows the story split three ways instead of a gauge that never moves.
> **A third problem surfaced on the second live run, and it was the worst of the three:** the
> summarizer's output cap was 750 tokens, and the loaded reasoning model spent all of it thinking,
> so every pass got an empty reply and wrote nothing. Layer 01 had been silently doing nothing on
> that model since S023. The cap is now a real setting that covers the thinking as well as the
> recap, an empty reply is retried once at double the cap, and a pass reports what it did so the
> panel can say "the model returned no recap" instead of looking successful. **Verified live:**
> the same session that wrote nothing now folds turns 36 to 40 into a 233-token recap.
> **Follow-up to S023.** No new table, no migration, no change to the turn path.

# S029 · Memory window status, and running the summary by hand

**Status:** ✅ COMPLETE — 2026-08-11.
**Depends on:** **S023** — memory layer 01, see
[archive](S023-2026-08-10-memory-layer-01-rolling-summary.md).
**Effort:** ~half a day
**Risk:** Low — read-only, apart from one operator action that runs the same pass the worker
already runs.

## Problem

S023 shipped the recap and showed its text. It showed nothing about *when* the next recap
would be written. An operator watching a session could not tell whether the story was near the
fold line or far from it, and had to play a turn to find out. There was also no way to make a
recap on demand, which made the layer awkward to try out on an old session.

## Scope

- [x] `RollingSummaryStatus` in `core/memory/rolling_summary_source.py`, plus a `status()`
      method on the source. It is a read-only twin of the first half of `observe`: the same
      walk, the same marks, so the panel and the worker cannot disagree about what is due.
- [x] `_WindowMarks` gained `window_tokens`, so one walk now answers both "where are the
      marks" and "what does the window cost".
- [x] Token totals stop at the window edge. Older messages are counted, not priced, for the
      reason S022 gave: pricing them means counting the whole history on every read.
- [x] `AdminService.get_session_memory` returns the three parts the panel needs in one call —
      which layers run, the status, and the recap. `AdminService.refresh_session_summary` runs
      the pass and returns the same shape.
- [x] The composition root builds one `RollingSummarySource` and gives it to both the pipeline
      and the panel. The panel must not measure a session with a different instance than the
      one that writes the recap.
- [x] Endpoints: `GET /admin/sessions/{id}/memory`, `POST /admin/sessions/{id}/memory/refresh`,
      and `PUT /admin/sessions/{id}/memory` now returns the same panel payload. The narrower
      `GET /admin/sessions/{id}/summary` from S023 is gone — one read for the whole panel beats
      two that can disagree.
- [x] Session page: the story map, the next-fold gauge, a bar for the recap against its share,
      the counts behind all three, and the **Run summary now** button. The first version gauged
      the window against the fold line; see "What the live run changed" below.
- [x] `min_fold_share` on the source and `RP_ENGINE_MEMORY_SUMMARY_MIN_FOLD_SHARE` in settings.

## Two decisions

**The manual run is inline, not queued.** Submitting to the background worker would return at
once and tell the operator nothing. The button waits for the model instead, which is honest:
the panel reports what the pass actually left behind. A pass with nothing to fold returns
immediately, because that is the same answer the worker would give.

**The manual run works even when the layer is switched off for that session.** An operator who
wants to read a recap before deciding whether to switch the layer on should be able to make
one. The recap simply does not reach any prompt until the layer is on.

## Known cost

Opening a session page walks the window and counts tokens for the messages inside it. The
counts are cached per message and per model, so only the first open of a session pays for it.
An unreachable LM Studio falls back to the character-ratio estimate and never fails the page.

## What the live run changed

Pablo ran the button on a 41-turn session and reported: *"Window against the fold line —
21492 / 17202 tokens (100%), then the recap is only 11 of the 41 turns. My idea was that the
window would shrink below the trigger. It is a bit confusing."*

Both halves of that were fair, and the numbers were right.

* **The window cannot shrink.** Folding a turn into the recap does not delete it. Layer 00 keeps
  replaying the newest turns that fit, so the bar reads full from the first fold onward. The gauge
  measured something that never moves.
* **In that session nothing had been lost at all.** 21492 tokens still fit inside the 22936-token
  budget, so all 41 turns still reached the model. The recap covered the oldest 11 as a
  precaution. The panel gave no way to see that.
* **The engine was doing too much work.** Each new turn pushed one more turn past the fold line,
  so the next pass had something to fold every single turn: one model call per turn, to add one
  turn to a paraphrase.

Fixed by:

1. **A fold batch.** `min_fold_share` (10% of the budget by default) is how much has to pile up
   before a pass spends a model call. The constructor refuses a batch larger than the slack the
   high-water mark leaves, so waiting turns always sit where the window can still replay them.
2. **A story map instead of a gauge.** The panel now shows the turns as three parts that add up
   to the whole story: in the recap, waiting to fold, and replayed word for word. Under it, one
   line says whether every turn still reaches the prompt.
3. **A next-fold gauge that fills and empties** — waiting tokens against the batch — which is the
   behavior the window bar wrongly implied.

## The second live run: the pass was writing nothing at all

Pablo pressed the button again and reported the gauge still full. Green means turns *are*
waiting, and a fold empties the gauge, so the pass had to be finding work and then writing
nothing. Running the same pass against his session and model showed why in one line of log:

```
LmStudio.generate with config { "maxTokens": 750, ... }
LLM response content:            ← empty
WARNING - The summarizer returned nothing; the recap is unchanged.
```

The cap came from the word target (`target_words * 3`). That covers the recap and nothing else,
but a reasoning model writes its thinking into the same budget, so the budget was gone before the
recap started. This is the failure S027 already fixed once on the story path, repeated in the
summarizer. On that model, layer 01 had been writing nothing since S023 — the recap Pablo saw
covering 11 turns was the one pass that happened to fit.

Fixed by:

1. **A real output cap.** `RP_ENGINE_MEMORY_SUMMARY_MAX_TOKENS`, 6144 by default, sized for the
   thinking plus the recap. It is no longer derived from the word target, because the word target
   describes the recap alone. The default is measured: on the loaded model, folding five turns
   returned nothing at 3072 and wrote a 233-token recap at 6144. A cap costs nothing when the
   model stops early, so it is set where the first attempt usually succeeds.
2. **One retry at double the cap** when the reply carries no text. How much a model spends on
   reasoning varies with the input, so no single number is safe. The call is in the background,
   so the retry costs no player time.
3. **The pass reports what it did.** `RollingSummarySource.fold` returns a `FoldOutcome`
   (`folded`, `condensed`, `waiting_for_batch`, `up_to_date`, `model_wrote_nothing`,
   `nothing_to_do`), the panel prints it under the button, and `observe` still discards it.
   A pass that wrote nothing must never look like one that worked. That is what cost two rounds
   of "is the button broken?".

## Verification

- [x] Unit, the status (6 cases): a story with nothing waiting reports zeros for the batch and
      counts every turn as replayed word for word; a full window names the turns ready to fold;
      the recap's coverage and what it still misses are reported; the batch filling up is
      reported as tokens against the batch; **`status()` changes nothing**; an empty session
      reports zeros.
- [x] Unit, the batch (4 cases): a single waiting turn is not worth a model call; a full batch is
      folded; a recap behind the window edge folds whatever the batch says; a batch larger than
      the slack is refused by the constructor.
- [x] Unit, the service: the panel payload carries the recap, the settings and the worker's own
      numbers; a manual run folds the story and returns the result; an unknown session returns
      `None` on both paths.
- [x] Unit, the endpoints: the status is served, a toggle returns the refreshed panel, the
      manual run reports the recap, and both paths report 404 for an unknown session.
- [x] Unit, the summarizer (7 cases, a new file): the configured cap is used; **an empty reply is
      retried once at double the cap**; two empty replies give up instead of looping; nothing to
      fold asks the model nothing; the recap comes back as one block of plain text.
- [x] Unit, the outcomes (6 cases): every `FoldOutcome` is produced by the state that means it,
      including `model_wrote_nothing` with nothing saved.
- [x] `uv run pytest` green (764 passed) · `uv run mypy src` clean · `uv run ruff check .`
      clean · the panel type-checks and builds.
- [x] **Live in the panel, first run (2026-08-11):** found the gauge and the per-turn folding.
- [x] **Live against the real model and database (2026-08-11):** reproduced the empty reply on
      session `1fb0ea29` (77 turns, 2320 tokens waiting against a 2293 batch), which is what
      identified the cap. **Then verified the fix end to end on the same session:** the first
      attempt still came back empty at 3072, the retry at 6144 wrote a 233-token recap, and the
      watermark moved from turn 35 to turn 40. Two attempts took 331 seconds, which is why the
      default cap is now 6144 rather than 3072 — one attempt instead of two.
- [ ] **Live in the panel, second run: open.** Read the story map on the same 41-turn session,
      play a few turns, and watch the next-fold gauge fill and empty instead of sitting at full.
