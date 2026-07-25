# S012 · Admin panel — thinking trace + per-message debug menu

**Status:** 🔵 Backlog
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
- Postgres backend: `GenerationTraceStore`/`ConversationStore` are dict/metadata-shaped already
  (no schema migration expected — `metadata` is a JSON(B) column and trace `record` is a JSON
  blob) but confirm no column-level allowlist filters out unknown metadata keys before shipping.

## Tasks

### Backend
- [ ] `LLMResponse.thinking: str | None` field.
- [ ] `LMStudioProvider._generate_sync` captures `parts[0]` as `thinking` instead of discarding it.
- [ ] `ChatService._narrator_message` stamps `thinking` (if present) and `turn` into the
      CHARACTER message's metadata.
- [ ] `ChatService._append_generation_trace` includes `thinking` in the trace record.
- [ ] Contract/unit tests: LM Studio provider reasoning-split test with `thinking` populated;
      `ChatService` test asserting stored message metadata carries `turn` (+ `thinking` when the
      fake provider returns one).

### Frontend
- [ ] Remove the global "Show generation traces" section from `SessionDetailPage.vue`.
- [ ] Add always-visible turn number display per CHARACTER transcript entry.
- [ ] Add per-message filter row (Thinking / Raw trace / System prompt / Turn metadata
      checkboxes) with independent local state per message and inline expand, gated so
      "Thinking" is absent/disabled when there's nothing to show for that message.
- [ ] Typecheck + production build clean (no test harness exists yet per S009 known gaps).

## Verification

- [ ] `uv run pytest` green, `uv run mypy .` clean, `uv run ruff check .` clean.
- [ ] Live-verified against a real thinking-capable model in LM Studio: confirm `thinking` is
      captured, persisted, and only shown in the UI for messages that have it.
- [ ] Frontend eyeballed in a browser: turn numbers correct, `...` menu opens/closes per message
      independently, system-prompt view matches the trace's actual prompt for that turn.
