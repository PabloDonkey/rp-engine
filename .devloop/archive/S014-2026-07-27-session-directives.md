> 🗄️ **ARCHIVED — COMPLETED 2026-07-27.** Frozen; do not edit. Kept as evolution history.
> **Result:** Three player controls sharing one mechanism — `/director` (one turn, cleared by
> the generation that consumes it), `/rule add|remove`/`/rules` (persistent, never-reused ids),
> `/language` (persistent). New `SessionDirectives` value object on `ScenarioSession`, stored in
> a dedicated `scenario_sessions.directives` JSONB column (migration `20260726_0008`, verified
> reversible against the real dev DB with 13 live sessions). `ConversationBuilder` gained
> Language → Scenario Rules → Director Instructions, placed after Response Format and before the
> memory hint, omitted cleanly when empty. Admin panel session detail surfaces all three
> read-only. Live-verified over Telegram: directives appear in the system prompt and are acted
> on by the model.
> **Produced ADR-025** (session reset tiers): `/restart` preserves player-owned settings,
> `/clear` resets them — generalized from this epic's restart carry-over decision. The `/clear`
> half is owned by S015.
> **Live testing also surfaced three provider bugs**, now boarded separately: `finish_reason`
> and token usage were never read from the SDK (fixed in `3061d6b`), and S017/S018/S019 cover
> the assistant-role mapping bug, prefill continuation, and reasoning-marker parsing.

# S014 · Session directives — Director Mode, Scenario Rules, Language preference

**Status:** ✅ COMPLETE — archived 2026-07-27
**Effort:** ~2-3 days (three related features sharing one mechanism)
**Risk:** Medium (touches `ConversationBuilder` prompt layout + session persistence + Telegram
command surface)

## Context

Three new user-facing controls that all work the same way — a Telegram command writes into
the session's directives, `ConversationBuilder` injects a dedicated system-prompt section
from them — but differ in persistence/lifetime:

| Feature | Command(s) | Lifetime | Prompt section |
|---|---|---|---|
| Director Mode | `/director <instruction>` | one-turn (auto-cleared after generation) | Director Instructions |
| Persistent Scenario Rules | `/rule add <instruction>`, `/rules`, `/rule remove <id>` | persistent per session until removed | Scenario Rules |
| Language preference | `/language <code>` (`en`, `fr`, `auto`, …) | persistent per session | Language |

Bundled as one epic because they share the same plumbing (session field +
`ConversationBuilder` section + Telegram command parsing) and the recommended system-prompt
layout interleaves them.

A **User Persona** section is scoped entirely to [S015](S015-user-persona-capture.md).

## What was built

### Domain — `core/scenario/session_directives.py`
- `SessionDirectives` (frozen): `language`, `rules: tuple[ScenarioRule, ...]`,
  `director_instruction`. Every mutator returns a new instance; validation (supported
  language codes, non-empty text) and rule-id allocation live here, not in the adapter.
- `ScenarioRule(id, text)`. **Ids are monotonic per session and never reused**, so an id a
  player read from `/rules` keeps pointing at the same rule after other rules are removed.
- `SUPPORTED_LANGUAGES`: `auto`, `en`, `es`, `fr`, `de`, `it`, `pt`, `ru`, `ja`, `zh`.
  `auto` is the default and means "emit no language section at all".
- `ScenarioSession` gains `directives` + `with_directives(...)`.

### Storage decision — a dedicated JSONB column, not session metadata
`scenario_sessions.directives` (migration `20260726_0008`, reversible). Rationale: the three
controls are read/written as a unit and never queried individually, `metadata` is a flat
`dict[str, str]` that would have forced JSON-inside-a-string for the rules list, and a
dedicated column keeps the admin panel and export payload legible. Pre-existing rows hold
`{}` → deserializes to the neutral defaults, so nothing needed backfilling.

### ConversationBuilder
Sections appended after `[Response Format]`, before the memory hint:
`Language → Scenario Rules → Director Instructions`. Empty sections are omitted entirely
(no bare headers). `{{char}}`/`{{user}}`/`{{world}}` are resolved inside them. The session's
`[Scenario Rules]` are deliberately distinct from the scenario card's own `[Rules]`.

### Director lifecycle
`ChatService` clears the instruction **after a successful generation** (`send_message`,
`continue_story`, `regenerate_last_response`) — a failed turn keeps it alive for the retry
the player is about to make. `PlaythroughService.restart` carries `language` + `rules` into
the fresh session but drops the pending director note.

That restart carry-over was an implementation judgement call here; it has since been
generalized into **ADR-025** (session reset tiers: `/restart` preserves player-owned
settings, `/clear` resets them). The `/clear` half is owned by
[S015](S015-user-persona-capture.md) — nothing in S014 needs to change for it.

## Tasks

### Domain / session persistence
- [x] `SessionDirectives` + `ScenarioRule` value objects, `ScenarioSession.directives`.
- [x] Storage shape decided (dedicated JSONB column) + reversible migration `0008`.
- [x] Shared serializer (`session_directives_to_payload` / `_from_payload`), malformed and
      missing payloads degrade to defaults rather than failing the session load.

### ConversationBuilder
- [x] Three new sections in the documented order; omitted cleanly when empty.
- [x] Director instruction read-and-cleared post-generation in `ChatService`.

### Application
- [x] `SessionDirectiveService` — the only writer of directives; adapters never touch
      `ScenarioSessionStore`.

### Telegram adapter
- [x] `/director <instruction>` (no arg → usage, or shows the queued note).
- [x] `/rule add|remove|list` + `/rules`.
- [x] `/language <code>` — validated against `SUPPORTED_LANGUAGES`, no arg → current + list.
- [x] Group policy matches the other story controls: administrators/creators only.
- [x] Help text + `set_my_commands` menu updated.

### Admin panel
- [x] Session detail shows `language` / `scenario_rules` / pending `director_instruction`
      (read-only) — `AdminSessionResponse.directives`, rendered above the transcript.

## Verification
- [x] Unit tests: builder renders/omits each section and orders them correctly; director
      instruction clears after one turn and survives a failed generation; domain rule-id
      reuse; serializer degradation paths; adapter command wording + group policy.
- [x] Contract test: directives round-trip and update-in-place through the Postgres session
      store (also exercised by the migrate-then-contract suite).
- [x] Migration verified reversible against the **real dev Postgres** (13 live sessions):
      `upgrade head` → column present with `'{}'::jsonb` default and legacy rows loading as
      defaults → set language/rule/director on a real session and re-read → `downgrade -1`
      (column gone, 13 sessions intact) → `upgrade head`. Test row restored to defaults.
- [x] `uv run pytest`: 319 passed (1 pre-existing failure,
      `test_scenario_catalog_dirs_defaults_to_data_catalog`, caused by
      `RP_ENGINE_SCENARIO_CATALOG_DIRS` being exported in the dev shell — unrelated).
      mypy clean on `src/`, ruff clean, frontend typecheck + build clean.
- [x] **Live-verified over Telegram** (2026-07-27): directives are present in the system
      prompt and visibly acted on by the model, confirmed via the admin panel's per-message
      *System prompt* and *Thinking* filters (S012).
