> 🗄️ **ARCHIVED — COMPLETED 2026-08-02.** Frozen; do not edit. Kept as evolution history.
> **Result:** Reasoning is now separated by **LM Studio's own fragment classification**
> (`on_prediction_fragment` → `LlmPredictionFragment.reasoning_type`), not by regexing the
> internal `__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_<hex>__` marker. The marker
> survives only as a fallback that **logs when it fires**, and a looser marker detector now
> refuses to deliver text it could not split (`LLMGenerationError`) instead of passing the
> model's whole reasoning to the player as the story. `reasoning_parsing` is exposed as an
> opt-in pair of settings rather than forced, because hard-coding `<think>`/`</think>` would
> break any model LM Studio parses differently. Live-verified against a reasoning-emitting
> model: 414 reasoning fragments captured as `thinking`, 65 prose fragments delivered clean,
> nothing marker-shaped in the reply.

# S019 · Use the SDK's `LlmReasoningParsing` instead of regexing an internal marker

**Status:** ✅ COMPLETE (2026-08-02)
**Effort:** ~half a day (as estimated)
**Risk:** Low-Medium — it changes how thinking is separated from prose, and prose is what the
player sees. Getting it wrong shows reasoning in the story.

## Problem

`LMStudioProvider._generate_sync` separated reasoning from the reply by regexing an
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
changed shape the regex would silently stop matching — and then **the model's entire reasoning
is delivered to the player as the story**, because `parts[-1]` becomes the whole blob.

## What was actually built

The epic assumed the fix was to *declare* the delimiters via `LlmPredictionConfig
.reasoning_parsing`. Reading the installed SDK (1.5.0) turned up a better primary signal:
`LLM.respond()` accepts `on_prediction_fragment`, and every `LlmPredictionFragment` carries a
`reasoning_type` of `none` / `reasoning` / `reasoningStartTag` / `reasoningEndTag` — LM Studio's
**own** classification, which no longer depends on the delimiter shape at all. `respond` still
returns the full `PredictionResult`; the callback runs alongside it, so this is not a switch to
a streaming API.

Order of precedence in `_separate_reasoning`:

1. **Fragment classification** (primary) — `reasoning` fragments become `thinking`, `none`
   fragments become the reply, and the two tag types are dropped (they *are* the delimiters).
   Skipped for structured predictions, whose value is `result.parsed`, not reassembled text.
2. **Marker split** (fallback) — used when no fragments arrived, or when a marker turns up
   inside text LM Studio classified as prose (i.e. it did not recognize this model's tags).
   **Logs a warning either way**, since reaching it means the supported path failed.
3. **Refuse** — a looser `__LM_STUDIO_INTERNAL_[A-Za-z0-9_]*__` detector catches a marker whose
   shape drifted out of what the fallback can split, and raises `LLMGenerationError` rather than
   delivering the blob. `generate` gained an `except LLMError: raise` arm so the catch-all no
   longer flattens that diagnosis into a generic failure.

`reasoning_parsing` is set only when both `RP_ENGINE_LMSTUDIO_REASONING_START_TAG` and
`..._END_TAG` are configured — a deliberate **deviation from the epic's "make the delimiters
ours"**: forcing `<think>`/`</think>` on every prediction would break any model whose reasoning
is delimited differently, and the fragment classification is derived from LM Studio's per-model
defaults. Half a pair raises at construction rather than at the first generation.

## Tasks

- [x] Set `reasoning_parsing` explicitly in `_get_config` — done as an opt-in pair of settings
      (see the deviation above), wired through `Settings` → `build_container`, documented in
      `.env.example`.
- [x] Split on the SDK's classification rather than the internal regex; the regex is kept as a
      defensive fallback **and logs when it fires**.
- [x] **Fail loudly, not silently, when separation fails.** Policy: refuse
      (`LLMGenerationError`). The *reasoning-only* case (prose empty, thinking captured) is
      deliberately left to `ChatService._require_content`, which already turns it into an
      `EmptyGenerationError` and leaves the conversation untouched for a retry.
- [x] Checked interaction with models that emit no reasoning (all fragments `none` → `thinking`
      is `None`) and with `structured`/`parsed` results (fall back to `_extract_content`).
- [x] `thinking` still reaches the admin transcript's per-message filter (S012) — the
      `LLMResponse.thinking` contract is unchanged.

## Verification

- [x] Unit (`tests/unit/infrastructure/test_lmstudio_provider.py`, 28 tests): fragment split,
      no-reasoning output, reasoning-only output (content `""`, never prose), marker inside
      prose fragments → fallback, drifted marker → refused, delimiters declared only when
      configured, half-configured pair rejected.
- [x] `uv run pytest` 439 passed · `uv run mypy .` at baseline (`src/` clean) · `uv run ruff
      check .` clean.
- [x] **Live** (2026-08-02, `gemma-4-e4b-it-uncensored@q4_k_m` via the real provider, SDK tapped
      to observe raw fragments):
      - 1500-token budget → `{'reasoning': 414, 'reasoningEndTag': 1, 'none': 65}`, finish
        `stop`, full chain-of-thought in `thinking`, two clean sentences of prose in `content`,
        **marker present in the raw stream, absent from the reply**.
      - 300-token budget → the model spent the entire budget thinking: `content == ""`, finish
        `length`, reasoning captured. This is exactly the case `_require_content` rejects, and
        it is what the old code would have shown the player as the story.
      - With `reasoning_start_tag="<think>"` / `reasoning_end_tag="</think>"` declared, LM Studio
        accepted the config and parsing still held.

## Relationship to other work

- [S018](S018-2026-07-27-prefill-continuation.md) wanted the exact delimiters if it ever emits a
  closed think block in a prefill; they are now declarable via config instead of guessed.
- Same class of defect as [S017](S017-2026-07-27-lmstudio-assistant-role-mapping.md): a tolerant
  probe around an unverified SDK assumption, degrading silently instead of failing. That class
  is now cleared out of the provider.
- **S012's** remaining "exercise a real thinking-capable model" is satisfied at the provider
  layer by the live run above; only its browser eyeball of the per-message Thinking filter is
  still outstanding.
