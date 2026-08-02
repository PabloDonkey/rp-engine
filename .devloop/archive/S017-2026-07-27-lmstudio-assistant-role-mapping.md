> 🗄️ **ARCHIVED — COMPLETED 2026-07-27.** Frozen; do not edit. Kept as evolution history.
> **Result:** Fixed the mapper sending every narrator reply as a **user** message.
> `add_assistant_message` does not exist on `lms.Chat`; the real method is `add_assistant_response`.
> The `getattr` probe silently fell back to the wrong role, so every character reply was seen by
> the model as user input — the player wrote both halves of the roleplay. Also exposed a latent
> incompatibility: `lms.Chat` rejects consecutive assistant responses, which becomes a real error
> once the correct role is sent. The mapper now collapses runs of narrator messages into one
> assistant turn, joining direct after a `length` stop and with a paragraph break otherwise.
> End-to-end verified against the live model.

# S017 · LM Studio mapper sends every narrator reply as a *user* message

**Status:** ✅ COMPLETE — archived 2026-07-27, awaiting the live quality read
**Effort:** ~1 hour for the fix; the value is in re-judging output quality afterwards
**Risk:** Low to fix, high impact — it changes what every prompt looks like to the model
**Found:** 2026-07-27, while probing LM Studio continuation behaviour for [S018](S018-prefill-continuation.md)

## Problem

`LMStudioConversationMapper._add_assistant_message`
(`infrastructure/llm/lmstudio/conversation_mapper.py:37-48`) probes for a method that does
not exist and silently falls back to the wrong one:

```python
add_assistant = getattr(chat, "add_assistant_message", None)   # never present
if callable(add_assistant):
    add_assistant(content)
    return
add_user = getattr(chat, "add_user_message", None)             # always taken
if callable(add_user):
    add_user(f"{content}")
```

The LM Studio SDK's method is **`add_assistant_response`**. `lms.Chat` has no
`add_assistant_message` (verified against the installed SDK 1.5.0):

```
['add_assistant_response', 'add_entry', 'add_system_prompt',
 'add_tool_result', 'add_tool_results', 'add_user_message', 'append', 'copy', 'from_history']
```

So **every narrator reply in history is sent to the model as a `user` message.** The model
never sees its own prior output as its own. From its point of view the player has been
writing both halves of the roleplay.

The `getattr` probing is what hid this: written to tolerate an unknown SDK shape, it turned a
wrong method name into a silent behavioural downgrade instead of an `AttributeError`.

## Likely consequences (to confirm by eye after the fix)

- Weaker character consistency and voice — the model has no assistant-turn continuity to
  anchor on.
- Confusion about who did what, and a tendency to narrate for the player.
- Reasoning models re-deriving context every turn, since nothing in the transcript is theirs.
- **Blocks [S018](S018-prefill-continuation.md) entirely**: prefill continuation requires the
  final message to genuinely be an assistant message.

## Outcome (2026-07-27)

Fixed. The `getattr` chain is gone — the mapper binds `add_assistant_response` directly.
Removing it **immediately caught a second stale double**: `FakeChat` in
`test_lmstudio_provider.py` also defined `add_assistant_message`, so it failed loudly the
moment the real name was bound. That is the behaviour the epic asked for, demonstrated on its
own first run.

The same probe-then-fallback shape in `_get_config` (`stop`/`stop_sequences`/`stop_strings`)
was also removed — `stop_strings` is now passed to the constructor. It was correct only by
accident, since no earlier name exists on `LlmPredictionConfig`.

Verified end to end against the live model: a resume prompt returned an in-character
continuation, which requires the assistant role to be right.

**Live testing then exposed a latent incompatibility the bug had been hiding.** `lms.Chat`
rejects consecutive assistant responses (`Multi-part or consecutive assistant responses are
not supported`), but consecutive narrator turns are ordinary here — `/continue` advances with
no player turn between, a resumed reply is stored as its own message, and a playthrough opens
with a narrator message. While every reply was mis-sent as `user`, the constraint was never
reached; sending the correct role hit it on the first `/retry`.

The mapper now collapses runs of narrator messages into one assistant turn, joining directly
after a turn that stopped at `length` (the rest of that sentence) and with a paragraph break
otherwise (a separate beat). Reproduced and fixed against the **real** SDK, not a double —
and both `FakeChat` doubles now enforce the constraint, since a double weaker than reality is
what let this reach production in the first place.

## Tasks

- [x] Call `chat.add_assistant_response(content)`.
- [x] **Delete the `getattr` fallback chain.** Bind to the real method and let a missing one
      raise. A silent fallback to the wrong role is worse than a crash on an SDK upgrade —
      that is the whole lesson of this bug.
- [x] Assert on roles, not just call success: build a `Conversation` with a character reply,
      map it, and check the resulting entries are `['system', 'user', 'assistant', …]`. The
      existing mapper tests pass today *with the bug present*, so role assertions are the
      point.
- [x] Grep for the same `getattr`-probe-then-fallback shape elsewhere in the provider
      (`_extract_content` and the `stop`/`stop_sequences`/`stop_strings` loop in `_get_config`
      use it too) and note any that could fail silently the same way.

## Verification
- [x] Unit: mapper emits `assistant` entries for `ConversationRole.CHARACTER`, and a
      multi-turn history alternates user/assistant.
- [x] Live: play several turns and compare voice/consistency against the current behaviour.
      This is a qualitative change — the tests can only prove the roles are right.
