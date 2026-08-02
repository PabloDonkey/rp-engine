> 🗄️ **ARCHIVED — COMPLETED 2026-08-02.** Frozen; do not edit. Kept as evolution history.
> **Result:** Model "thinking" is captured instead of discarded, rides the CHARACTER message's
> metadata alongside its turn number, and the transcript's session-wide "Show generation traces"
> dump is replaced by an independent per-message filter row (Thinking / Raw trace / System prompt
> / Turn metadata). Built and data-flow-verified 2026-07-24; the two verification gaps closed on
> 2026-08-02 — [S019](S019-2026-08-02-lmstudio-reasoning-parsing.md) exercised a real
> reasoning-capable LM Studio model (and replaced the marker regex this epic relied on with the
> SDK's fragment classification), and Pablo eyeballed the filter UI in a browser.

# S012 · Admin panel — thinking trace + per-message debug menu

**Status:** ✅ COMPLETE (2026-08-02) — backend + frontend built and end-to-end data-flow verified
(2026-07-24); the live-model and browser-eyeball gaps closed 2026-08-02, see Verification.
**Effort:** ~1 day
**Risk:** Low (additive metadata + frontend-only restructuring of an existing debug view)

## Context

Follows S009 (admin panel MVP, session/conversation debugging). Today the transcript's
`content` for a CHARACTER message is only the *final* text — when a model has thinking/reasoning
enabled, LM Studio returns an internal reasoning block glued to the reply, delimited by a
`__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_<hex>__` marker
(`LMStudioProvider._generate_sync`, `src/rp_engine/infrastructure/llm/lmstudio/provider.py:82-90`).
The provider currently splits on that marker and **keeps only `parts[-1]`** — the reasoning text
(`parts[0]`, and anything before the marker) is discarded and never persisted anywhere, not even
in the generation trace.

Separately, the debugging UX on `SessionDetailPage.vue` is coarse: a single "Show generation
traces (N)" toggle at the bottom of the whole transcript dumps every raw trace record for the
session. There's no way to jump from one character reply to *its* trace, its system prompt, or
(once captured) its thinking — you have to eyeball timestamps/turn numbers across two lists.

**Requested UX (2026-07-24, Pablo — refined via PO interview):**
- Each CHARACTER transcript entry gets an inline **filter row** (checkboxes/chips, not a
  dropdown menu): **Thinking**, **Raw trace**, **System prompt**, **Turn metadata**
  (finish_reason/latency/usage). Checking one expands that data block inline under *that*
  message — this is per-message "see one answer's data," not a session-wide dump.
  - The filter selection is **per-message, not global** — each message's checkboxes are
    independent and don't carry over when you open another message's filter row.
  - "Thinking" is absent/disabled when that message has no captured thinking content.
  - No global "Show generation traces" section at the bottom of the page anymore — it's fully
    replaced by these per-message filters.
- Each transcript entry (character replies) always shows its **turn number** in the header,
  independent of the filter row — "Turn metadata" as a filter is the *extra* detail
  (finish_reason/latency/usage), not the turn number itself.
- Only CHARACTER messages get the filter row; USER messages stay plain transcript rows (no
  thinking/system-prompt/trace concept for them).

## Architecture fit

Core stays framework-free; this is a provider-level capture + existing metadata plumbing +
frontend page rework. No new ports needed.

- **`core/llm/response.py`** — `LLMResponse` gains an optional reasoning field (e.g.
  `thinking: str | None = None`) alongside `content`/`finish_reason`/`metadata`.
- **`LMStudioProvider._generate_sync`** — when the reasoning marker is present, keep `parts[0]`
  (stripped) as `thinking` instead of discarding it; `None` when the model didn't emit one (no
  marker found, or thinking disabled for that model).
- **`ChatService`**:
  - `_narrator_message` (`application/services/chat_service.py:440`) already stamps
    `finish_reason` into `ConversationMessage.metadata` (`dict[str, str]`) — extend the same way
    with a `thinking` key (only when non-empty) and a `turn` key (str of `_resolve_turn(...)`,
    already computed at the call site but currently only fed into the trace record, not the
    stored message). This makes turn + thinking travel with the message itself, so the frontend
    doesn't need to cross-reference the trace list to render them — they ride the existing
    `AdminMessageResponse.metadata` passthrough (`adapters/api/admin_models.py:59-66`) with **no
    API contract change**.
  - `_append_generation_trace` (`chat_service.py:465`) — add `"thinking"` to the trace `record`
    dict for parity/completeness (trace already carries `turn`, `prompt`, `response`).
- **System prompt per message**: the generation trace already carries the full prompt used for
  that turn (`prompt_payload` via `_serialize_prompt`, plus `conversation.messages`). "Show system
  prompt" for a given transcript entry = find the trace whose `record.turn` matches the message's
  `turn` metadata (both now present) and render its `prompt`/system portion — no backend change
  needed beyond what "Show traces" already fetches via `GET /admin/sessions/{id}/traces`.

### Frontend — `SessionDetailPage.vue`

- Remove the bottom-of-page global "Show generation traces (N)" button + list.
- Per CHARACTER `<li>` in the transcript: always show a turn label (from `message.metadata.turn`),
  plus an inline row of independent filter checkboxes/chips — **local `ref` state per message**,
  not shared/global:
  - **Thinking** — `message.metadata.thinking` (checkbox absent/disabled if there's nothing to
    show for that message).
  - **Raw trace** — the raw trace record(s) matching this message's turn (reuse `store.traces`,
    already fetched with the session; filter client-side by `record.turn`).
  - **System prompt** — the `prompt` field from that same matched trace record.
  - **Turn metadata** — the small extras (`finish_reason`, `latency_ms`, token usage) pulled from
    the matched trace record — distinct from the always-visible turn *number* in the header.
  - Checking a box expands that data block inline under the message; unchecking collapses it.
    Each message's checkboxes are independent of every other message's.
- USER messages stay plain rows: no filter row, no thinking/system-prompt/trace concept — only
  CHARACTER replies are focusable/filterable, matching "see one answer of the character."

## Open questions

- Multiple trace records can share a turn (e.g. a retry) — decide whether "Show traces" for a
  message shows all of them or just the latest; leaning latest-first with a count badge.
  **Resolved in code:** `tracesForTurn` returns *every* matching record for the raw-trace list,
  while `systemPromptFor`/`turnMetaFor` read `latestTraceForTurn` — all of them where the raw
  dump is the point, latest-wins for the derived views.
- Postgres backend: `GenerationTraceStore`/`ConversationStore` are dict/metadata-shaped already
  (no schema migration expected — `metadata` is a JSON(B) column and trace `record` is a JSON
  blob) but confirm no column-level allowlist filters out unknown metadata keys before shipping.

## Tasks

### Backend
- [x] `LLMResponse.thinking: str | None` field (`core/llm/response.py`).
- [x] `LMStudioProvider._generate_sync` captures the reasoning-marker prefix as `thinking`
      instead of discarding it (`None` when the marker isn't present).
- [x] `ChatService._narrator_message` now takes `turn` and stamps `turn` (always) and `thinking`
      (when present) into the CHARACTER message's metadata, alongside the existing
      `finish_reason`. All three call sites (`send_message`, `continue_story`,
      `regenerate_last_response`) updated to pass `turn`.
- [x] `ChatService._append_generation_trace` includes `thinking` in the trace record.
- [x] Tests: `test_lmstudio_provider.py` — reasoning-marker split populates `thinking`, absence
      of the marker leaves it `None`. `test_chat_service.py` — narrator message metadata carries
      `turn` (existing assertions updated for the new key) and `thinking` when the provider
      returns one (new tests); generation-trace test asserts `thinking` on the record.

### Frontend
- [x] Removed the global "Show generation traces" section from `SessionDetailPage.vue`.
- [x] Always-visible turn number ("· Turn N") per CHARACTER transcript entry.
- [x] Per-message filter row (Thinking / Raw trace / System prompt / Turn metadata checkboxes)
      with independent `reactive` state keyed by transcript index, inline expand/collapse;
      "Thinking" checkbox is disabled when the message has no captured thinking.
- [x] Typecheck (`vue-tsc --noEmit`) and production build (`vite build`) both clean.

## Verification

- [x] `uv run pytest` green (247 passed / 12 skipped), `uv run mypy src` clean, `uv run ruff
      check .` clean. (Two pre-existing, unrelated mypy notes remain in
      `test_chat_service.py`/`test_main_endpoints.py`/`test_application_flow.py` — unchanged
      lines, confirmed via `git diff`, not introduced by this change.)
- [x] Frontend `typecheck` + production `build` clean.
- [x] **End-to-end data-flow verified** (scratchpad script, not committed): booted the real
      `FastAPI` app (`create_app`) against a disposable temp-dir JSON backend, seeded a real user/
      scenario/session through the actual JSON stores, and called the real `ChatService.
      send_message` with only the raw LLM call stubbed (`orchestrator.generate_reply` returning
      an `LLMResponse` with `thinking` set — no LM Studio needed). Confirmed through the real
      `/admin/sessions/{id}/transcript` and `/admin/sessions/{id}/traces` HTTP responses that:
      the stored CHARACTER message's `metadata` has `turn: "1"` and `thinking: "<text>"`; the
      trace record has `turn: 1`, `thinking: "<text>"`, `prompt.assembled_system_prompt`, and
      `finish_reason`/`latency_ms`/`usage` — exactly the shape `SessionDetailPage.vue`'s
      `tracesForTurn`/`systemPromptFor`/`turnMetaFor` helpers consume. Confirms the full
      contract end to end except the two points below.
- [x] **Closed 2026-08-02 by [S019](S019-2026-08-02-lmstudio-reasoning-parsing.md).** A real
      reasoning-capable model was exercised live: 414 reasoning fragments captured as `thinking`,
      65 prose fragments delivered clean. It also answered the question this epic could not —
      the marker text was *not* safe to assume, so the split now uses LM Studio's own
      `reasoningType` fragment classification and the regex survives only as a logged fallback.
      `LLMResponse.thinking` is unchanged, so everything downstream of it here is untouched.
      One seam is worth naming for whoever debugs this later: the live run proved the **provider**
      half, and the 2026-07-24 end-to-end run proved the **`ChatService` → transcript** half with
      the LLM stubbed. Both halves are verified; they have never run in a single pass.
      `chat_service.py::_narrator_message` is the join, and it is unit-tested.
- [x] **Closed 2026-08-02:** Pablo eyeballed the per-message filter UI in a browser and confirmed
      it renders as intended.
