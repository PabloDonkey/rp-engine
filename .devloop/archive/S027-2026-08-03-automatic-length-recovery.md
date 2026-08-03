> 🗄️ **ARCHIVED — COMPLETED 2026-08-03.** Frozen; do not edit. Kept as evolution history.
> **Result:** A reply that stops at `finish_reason: length` is now recovered **once,
> automatically**, in `ChatService`. Two shapes, picked from what came back: prose that was
> cut off is resumed as an assistant prefill and delivered as **one** turn; a reply with no
> prose at all (reasoning ate the whole budget) has nothing to prefill, so the original
> request is re-run with a larger cap (`RP_ENGINE_LMSTUDIO_LENGTH_RETRY_MAX_TOKENS`).
> `context_length` is deliberately **not** recovered. Fixed alongside: the provider stripped
> the leading space off a prefill continuation, which glued `"She reached for"` to
> `"the door"`; and the six `"Telegram failure"` log lines now name their reason in the
> message instead of only in `extra`, which the default log format drops.
> **Not live-verified** — unit tests only. See Verification.

# S027 · Recover automatically when the model runs out of tokens

**Status:** ✅ COMPLETE (2026-08-03) — awaiting a live check against a real playthrough
**Effort:** ~half a day
**Risk:** Medium — it adds a second LLM call to a turn that already failed, and it changes
what the player sees as "one reply".
**Builds on:** [S018](S018-2026-07-27-prefill-continuation.md) (assistant prefill),
[S019](S019-2026-08-02-lmstudio-reasoning-parsing.md) (reasoning separation).

> Story number: the README rule is "max existing id + 1", which would be S024. **S024–S026
> are reserved** on the board for the memory layers (lorebook, fact store, vector recall),
> so this epic takes **S027** rather than stealing a reserved id.

## Problem

Reported from a real playthrough at turn 85, with `RP_ENGINE_LMSTUDIO_MAX_TOKENS=2000`:

```
INFO  rp_engine.core.engine.orchestrator - Response generated
WARN  rp_engine.adapters.telegram.adapter - Telegram failure
```

The model spent all 2000 tokens reasoning and wrote no prose. `ChatService._require_content`
rejected the turn as an `EmptyGenerationError`, correctly — storing an empty narrator turn
would poison every later prompt. But the player just loses the turn and has to retry by hand.

This is the same failure [S018](S018-2026-07-27-prefill-continuation.md) already measured
("a resume spent its entire 2000-token budget reasoning and returned no prose at all"). S018
fixed the case where a *resume* caused it, by removing the reasoning pass. It did not cover a
first attempt that simply over-thinks.

Two situations end at `length`, and only one of them can be continued:

| | what came back | can it be resumed? |
|---|---|---|
| **A** | prose, cut mid-sentence | yes — prefill from those exact tokens |
| **B** | nothing; the budget went on reasoning | no — there are no tokens to prefill |

Both leave the player holding a broken turn, so both need recovering; they need different
shapes.

## Design

One helper, `ChatService._generate_recovering_length`, used by all three entry points
(`send_message`, `continue_story`, `regenerate_last_response`). It generates, and if the
reply stopped at `length` it makes **exactly one** more attempt:

- **A — resumable.** Build a `build_resume` conversation whose final assistant message holds
  everything written for this reply so far, then join both halves into one `LLMResponse`.
  "So far" includes any stored truncated text the request was *already* resuming, or a
  cut-off `/continue` would continue only its own half of the sentence.
- **B — nothing written.** Re-run the original conversation unchanged. Only the larger cap
  makes the second attempt different from the first, which is why the retry needs its own
  settings rather than reusing `generation_settings`.

Decisions worth keeping:

- **`context_length` is never retried.** The window is full; a second attempt hits the same
  wall. `FinishReason` already separated the two values — this is the first caller to depend
  on that separation.
- **One retry, then stop.** A second cap hit is stored with `finish_reason: length` exactly
  as before, so `/continue` still works by hand. The recovery shortens the common case; it
  does not become an unbounded loop.
- **Off unless wired.** `length_retry_settings=None` disables it, matching how
  `generation_trace_store` is optional. The composition root always supplies it.
- **Each attempt is traced separately.** An empty generation is exactly what you want a trace
  for, and the retry is a different prompt at a different cap.
- **Retry thinking falls back to the first attempt's.** A prefill continuation normally emits
  no reasoning of its own (S018), so the planning would otherwise be thrown away.

## Second bug, found while building it

`LMStudioProvider._separate_reasoning` ran `.strip()` on the prose. That is right for a normal
reply and wrong for a continuation: `"She reached for"` + `"the door"` renders as
`"She reached forthe door"`. It never showed before because `/continue` stores its halves as
two messages and Telegram sends them as two messages — the seam was a message boundary. Joining
them inside one turn exposed it.

A prefill continuation now keeps **one** leading space or newline. Only one: more than that is
model padding, not sentence glue. It applies only when nothing was classified as reasoning, so
a newline left over from a reasoning boundary cannot be mistaken for meaningful whitespace.

## Third fix: the log line that says nothing

`"Telegram failure"` was six different faults with identical text. `configure_logging` formats
`%(message)s` and drops `extra`, so the `reason` field was recorded and then thrown away — the
report that opened this epic could not be diagnosed from the log alone. Each arm now names its
reason in the message, and the empty-generation arm carries its `finish_reason` too, since that
is what tells an over-thinking model from a full context window.

## Tasks
- [x] `ChatService._generate_traced` — extract the generate-and-trace block the three entry
      points each had a copy of.
- [x] `ChatService._generate_recovering_length` — one retry, two shapes, `length` only.
- [x] `ChatService._resume_anchor` — where a resume picks the reply up from, so the three
      entry points do not each work it out.
- [x] Wire all three entry points through it.
- [x] `RP_ENGINE_LMSTUDIO_LENGTH_RETRY_MAX_TOKENS` setting (0 = no limit, same convention as
      `RP_ENGINE_LMSTUDIO_MAX_TOKENS`), documented in `.env.example`, wired in `app/main.py`.
- [x] Provider: keep the leading space on a prefill continuation.
- [x] Telegram adapter: fold `reason` into the `"Telegram failure"` message.
- [ ] Consider making the *default* retry cap bounded rather than unlimited. 0 follows the
      existing convention, but an unbounded retry is an odd default for a recovery path.

## Verification
- [x] Unit — truncated prose is resumed and delivered as one stored turn, carrying the retry's
      finish reason.
- [x] Unit — a reasoning-only reply re-runs the *same* conversation at the *larger* cap.
- [x] Unit — a second cap hit stops, and stores the turn as truncated.
- [x] Unit — `context_length` is not retried.
- [x] Unit — recovery is off when no retry settings are wired.
- [x] Unit — a cut-off `/continue` resumes from stored text plus new text, not new text alone.
- [x] Unit — both attempts are traced.
- [x] Provider unit — a prefill continuation keeps one leading space; keeps only one; is
      stripped as usual when it reasoned; a normal reply is still stripped.
- [x] `uv run pytest` 461 passed · `uv run mypy src` clean · `uv run ruff check .` clean.
- [ ] **Live** — reproduce the turn-85 case against the real model and confirm the player gets
      a reply instead of the empty-generation message. Not done; this epic was verified by
      unit tests only.
