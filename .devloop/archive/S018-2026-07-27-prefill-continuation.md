> 🗄️ **ARCHIVED — COMPLETED 2026-07-27.** Frozen; do not edit. Kept as evolution history.
> **Result:** `/continue` now uses assistant prefill instead of a "please continue" nudge.
> New `Conversation.continue_final_message` boolean; `build_resume` sets it and sends no
> directive turn, leaving the chat assistant-final. The mapper (S017 — required; prefill is
> impossible while assistant messages go out as user) maps that to `add_assistant_response`,
> which triggers LM Studio's prefill. Probed live against the local model: prefill continues
> mid-sentence, in character, with **no reasoning pass** (45 tokens vs. 2000+ spent reasoning
> then returning nothing). Removed the `<notes>` resume mitigation that was the fallback.
> End-to-end verified builder → mapper → provider against the live model.

# S018 · `/continue` by assistant prefill instead of a "please continue" nudge

**Status:** ✅ COMPLETE — archived 2026-07-27, awaiting the live Telegram check
**Effort:** ~1 day
**Risk:** Medium — changes the core→provider contract (a `Conversation` must be able to say
"the last message is a prefix to continue", not just "here is the history")
**Depends on:** [S017](S017-lmstudio-assistant-role-mapping.md) — prefill is impossible while
the mapper turns assistant messages into user messages.

## Problem

`/continue` on a truncated reply currently appends a **user** message ("Your previous reply was
cut off… write only the missing continuation"). That opens a **new assistant turn**, and a new
turn is when a reasoning model re-plans from scratch. Observed live: a resume spent its entire
2000-token budget reasoning and returned no prose at all.

The industry mechanism is **assistant prefill / prefix continuation**: put the partial
assistant text last and continue generating from those exact tokens, opening no new turn. In
llama.cpp's server (LM Studio is built on it) this triggers on a final `role: "assistant"`
message plus `chat_template_kwargs: {"add_generation_prompt": false}`. LM Studio's own UI
"Continue assistant message" is this feature. SillyTavern uses prefill where the backend allows
it and falls back to a nudge only where it doesn't — and its docs warn the nudge is unreliable:
*"Asking the AI to continue a message that it considers 'finished' does not usually work."*

## Probe result (2026-07-27) — measured, not assumed

Against the live local model via the LM Studio Python SDK, `max_tokens=64`:

| | construction | outcome |
|---|---|---|
| **A** | chat ends with `add_assistant_response("…stepped into the")` | **continued in place**: `" salt-thickened air of the gallery. The wood groaned…"` — and emitted **no reasoning at all** |
| **B** | control, ends with the user message | new turn, and **reasoned first** (planning text + the reasoning-end marker) |
| **C** | `model.complete(partial)` raw | **also reasoned** — treated the fragment as a task to analyse, not text to continue |

Three conclusions, all decisive:

1. **Assistant-final continuation works through the plain SDK.** No jinja override, no
   `chat_template_kwargs`, no REST bypass — `model.respond()` on an assistant-final chat
   continues the text.
2. **It removes the reasoning pass**, which is the actual cause of the empty turn. Prefill
   doesn't just phrase the request better, it deletes the work.
3. **`model.complete()` is not the answer** despite being the "raw continuation" API — it
   reasoned too. Rules out the option that looked most obvious from the docs.

This also supersedes the current mitigation (handing the previous turn's reasoning back as
`<notes>` in the resume directive, `ConversationBuilder._resume_directive_text`): that is the
fallback tier for backends without prefill. Keep it only if a non-prefill provider is ever
added; otherwise delete it, along with `RESUME_THINKING_MAX_CHARS` and
`ChatService._last_thinking`.

## Design

The core cannot keep expressing resume as "a user message that asks nicely" — it has to be able
to mark the conversation as *continuing its final assistant message*. Options:

- A flag on `Conversation` (e.g. `continue_final_message: bool`), with the mapper omitting the
  directive turn and ending on the assistant message. Simple; the port contract grows one
  boolean that non-prefill providers may ignore (degrading to today's nudge).
- A distinct `ConversationRole`/message kind for "assistant prefix". More expressive, more
  surface.

Prefer the boolean. Either way `ConversationBuilder.build_resume` stops appending a directive
message, and the truncated text must be the final message rather than merely present in history.

## Outcome (2026-07-27)

Built. `Conversation.continue_final_message` expresses the intent in the core; `build_resume`
appends **no** instruction turn and marks the conversation instead.

**The mapper needed no special path.** Mapping `CHARACTER` to `add_assistant_response` (S017)
already leaves the chat assistant-final, which is exactly what LM Studio continues. So the
flag's job is not to select a code path but to state intent — and to let the provider warn when
intent and shape disagree (`is_prefill`), which is what a memory strategy that trims or
reorders would cause.

End-to-end against the live model, builder → mapper → provider:

```
continue_final_message: True   last message role: character
finish_reason: stop            usage: prompt 197, completion 45, total 242
thinking captured: NONE (no reasoning pass)
continuation: 'frame. *He gripped the iron handle, his knuckles white...*  "Hm."'
```

It continued `"stepped into the"` → `"the frame."` mid-sentence, in character, with **no
reasoning pass** and 45 completion tokens — against the earlier failure that spent all 2000 on
reasoning and returned no prose. The `<notes>` mitigation is deleted, along with
`RESUME_THINKING_MAX_CHARS` and `ChatService._last_thinking`.

## Tasks
- [x] Land [S017](S017-lmstudio-assistant-role-mapping.md) first.
- [x] Extend `Conversation` to express "continue the final assistant message"; `build_resume`
      sets it and appends no directive turn.
- [x] `LMStudioConversationMapper`: no special path needed (see Outcome); added `is_prefill`
      plus a provider warning for the intent/shape mismatch case.
- [x] `LLMProvider` port doc: state that providers unable to prefill must fall back to the
      nudge, so the contract is explicit rather than implied.
- [x] Remove the `<notes>` resume mitigation (or demote it to the documented fallback).
- [x] Keep `_should_resume` as the trigger — the `finish_reason: length` plumbing it depends on
      is already correct.
- [x] Considered emitting a **closed think block** — **not needed**: the probe and the
      end-to-end run both show this model emits no reasoning at all under prefill.
      Revisit only if a model is found that reasons anyway.
- [ ] ~~Consider emitting a closed think block~~ in the prefill for models where reasoning is
      not skipped automatically (llama.cpp #21889 reports −8.64s and 456 tokens saved per
      request, no quality regression). Probe A suggests our model needs no such help; verify
      before building it, and see [S019](S019-lmstudio-reasoning-parsing.md) for the markers.

## Verification
- [x] Unit: a resume conversation ends on the assistant message and carries no directive turn.
- [x] Mapper: the final SDK entry is `assistant` and holds the partial text verbatim.
- [x] Live: truncate a reply, `/continue`, confirm the text resumes mid-sentence with no
      restatement and no reasoning pass; then `/retry` and confirm it resumes again (the
      `_should_resume` symmetry added alongside the nudge).
