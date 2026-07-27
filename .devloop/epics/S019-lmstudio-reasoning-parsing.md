# S019 · Use the SDK's `LlmReasoningParsing` instead of regexing an internal marker

**Status:** 🔵 Backlog
**Effort:** ~half a day
**Risk:** Low-Medium — it changes how thinking is separated from prose, and prose is what the
player sees. Getting it wrong shows reasoning in the story.

## Problem

`LMStudioProvider._generate_sync` separates reasoning from the reply by regexing an
**LM Studio internal marker**:

```python
parts = re.split(
    r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-f0-9]+__", content
)
clean_text = parts[-1].strip()
thinking = "\n".join(part.strip() for part in parts[:-1] if part.strip()) or None
```

The name says what it is: `INTERNAL`, `SYNTHETIC`, and a per-run hex suffix. It is not API,
carries no compatibility promise, and can change in any LM Studio release. If the marker ever
changes shape the regex silently stops matching — and then **the model's entire reasoning is
delivered to the player as the story**, because `parts[-1]` becomes the whole blob. That is a
user-visible failure, not a degraded log.

The SDK exposes the supported control (verified on the installed 1.5.0):

```
LlmReasoningParsing:
  enabled     (wire: enabled)     : bool
  start_string(wire: startString) : str
  end_string  (wire: endString)   : str
```

It is a field on `LlmPredictionConfig` (`reasoning_parsing`), i.e. we can *declare* the markers
we want rather than reverse-engineer whatever LM Studio picked.

## Tasks

- [ ] Set `reasoning_parsing` explicitly in `_get_config` so the delimiters are ours, not
      whatever the build defaults to.
- [ ] Split on the configured `end_string` (and honour `start_string`) rather than the internal
      regex. Keep the current regex only as a defensive fallback if it proves necessary — and
      if kept, log when it fires, since that means the primary path failed.
- [ ] **Fail loudly, not silently, when separation fails.** If reasoning cannot be split out,
      that must not land in the player's message. Decide the policy: treat it as an empty
      generation (`EmptyGenerationError`, already exists) or strip conservatively — but never
      pass an unsplit blob through as prose.
- [ ] Check how `reasoning_parsing` interacts with models that emit no reasoning at all, and
      with `structured`/`parsed` results.
- [ ] Verify the captured `thinking` still reaches the admin transcript's per-message Thinking
      filter (S012) unchanged.

## Relationship to other work
- [S018](S018-prefill-continuation.md) may want to emit a **closed think block** inside a
  prefill so reasoning is skipped (llama.cpp #21889). That requires knowing the exact
  delimiters — which is precisely what this epic makes explicit rather than guessed.
- The same class of defect as [S017](S017-lmstudio-assistant-role-mapping.md): a tolerant probe
  around an unverified SDK assumption, degrading silently instead of failing.

## Verification
- [ ] Unit: reasoning split against the configured delimiters, including no-reasoning output,
      reasoning-only output (must not be presented as prose), and a malformed/unterminated
      block.
- [ ] Live: a reasoning-capable model produces a clean reply with the reasoning captured
      separately and **nothing** marker-shaped in what Telegram sends.
