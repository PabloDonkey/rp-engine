# S015 · User persona capture on new session start (+ `/clear`)

**Status:** 🟢 **Code complete 2026-07-27** — 410 passed (1 pre-existing unrelated
failure: `test_scenario_catalog_dirs_defaults_to_data_catalog`, an env leak), `mypy src/`
clean, `ruff check` clean. Migration `20260727_0009` verified reversible against the real
dev Postgres with 13 live sessions (all 13 backfilled `updated_at = created_at`; partial
index created; downgrade restores the plain index and the data). **Landed together with the
core of [S016](S016-session-soft-delete-lifecycle.md)** — see the note under *Reset tiers*.
**Remaining: the live Telegram read.**
**Effort:** ~2 days (was ~1-2; `/clear` adds roughly half a day)
**Risk:** Medium — new pending-input mechanism in the Telegram adapter (nothing like it exists
today), a new immutable persisted field + Alembic migration, and a `{{user}}` resolution change.
**Design decisions:** locked in below (reply format, `/skip`, abandoned-prompt handling,
reset tiers) — ready for implementation, no open questions remaining.
**Depends on:** **ADR-025** (session reset tiers) — this epic implements the `/clear` half of it.
**Sequence with:** [S016](S016-session-soft-delete-lifecycle.md) (session soft delete) — land it
first or in the same change; `/clear` is a third path that supersedes a session.
**Resolved: S016's domain/persistence/store-semantics/service half landed in this change.**
What is left of S016 is its admin-panel presentation (superseded badge, session-list sort);
the API already returns `created_at`/`updated_at`/`deleted_at` and `AdminService.list_user_sessions`
opts into `include_deleted=True`, so the panel keeps today's visibility.

## Context

When `/play <id>` starts a **brand-new** session, the bot should ask the player to define
their character before the story intro is shown:

> "Please provide a name for your character, a description of what they are and their
> likes/dislikes. This cannot be changed once the play session has started. Send /skip to use
> your Telegram username with no description."

The player's next plain-text reply becomes the **user persona**: first line = name, remainder
= description (see **Reply format** below). The name is substituted for `{{user}}` everywhere,
replacing today's Telegram-display-name default; the description renders in a new
**User Persona** prompt section (static world state — not memory, per S014's layout notes).
Once set, it's immutable for the life of that session — no edit command. `/skip` falls back to
the Telegram username as the name, no description section.

`/resume`-style flows (an *existing* active session found by `PlaythroughService.start`, i.e.
`_resume` not `_begin`) do **not** re-ask — only genuinely new sessions do.

**Scope: `owner_kind == "user"` only, for now.** Group sessions keep today's behavior
(`{{user}}` resolves to the group's synthesized display name, no prompt, no persona). Revisit
later if group personas are wanted. **`/clear` itself is not user-scoped** — it is a session
reset like `/restart` and applies to groups too (group administrators only, like the other
story controls).

### Reset tiers — what changed since this epic was first written

S014 shipped `/restart` **carrying the player's persistent directives forward** (language +
scenario rules), on the reasoning that restarting the story is not a request to re-configure
it. **ADR-025** generalizes that into a rule, and the persona follows it:

| | conversation | world/story state | persona, language, rules |
|---|---|---|---|
| `/play <id>` (new session) | fresh | fresh | fresh — **prompts for persona** |
| `/play <id>` (existing session) | kept | kept | kept — no prompt |
| `/restart` | reset | reset | **preserved — no persona prompt** |
| `/clear` | reset | reset | **reset — prompts for persona** |

Two consequences for this epic as originally drafted:

1. **`/restart` must no longer re-prompt for a persona.** The first draft had `/play` *and*
   `/restart` both prompting (both go through `_begin`). Under ADR-025 the persona survives a
   restart like language and rules do, so only `_begin` calls that start from defaults prompt.
2. **`/clear` is not optional polish — it is what makes "immutable once set" survivable.**
   With `/restart` no longer resetting the persona, `/clear` becomes the *only* way to fix a
   typo'd name or change character. Shipping the immutability contract without it would strand
   players. That is why `/clear` lives in this epic rather than a follow-up.

### Why the persona needs new plumbing

Confirmed via exploration (`Explore` agent, see prior turn) that:
- The Telegram adapter is currently **fully stateless per message** — `handle_message` parses
  and dispatches a single update with no cross-message memory. The one precedent for small
  transport-local state is `TelegramNarratorStore`
  (`src/rp_engine/adapters/telegram/narrator_store.py`) — a tiny per-chat file-backed
  get/set/clear store used by `/retry`. A "waiting for persona reply" store should follow the
  exact same shape, keyed by `(owner_kind, owner_id)` like every other session-scoped lookup.
- `{{user}}` is resolved in `ConversationBuilder._resolve_templates` as
  `payload.user.display_name`, unconditionally — no per-session override exists.
  `payload.user` comes from `ChatService._load_scenario_context`, which for **group** sessions
  synthesizes a `User` from the `Group` — i.e. today a group's `{{user}}` is the group's name,
  not any one player's. A per-`ScenarioSession` persona field (not a `User`-level field) is
  therefore the right place to hook in, and resolves uniformly for both `owner_kind`s.
- `ScenarioSession` is a frozen dataclass with no persona field today. **S014 precedent:** it
  now carries `directives: SessionDirectives` in a dedicated `scenario_sessions.directives`
  JSONB column (migration `20260726_0008`) rather than in the `metadata` string bag — for the
  same reason the persona wants first-class fields: schema-visible identity, and an
  "immutable once set" contract enforceable in the type rather than by convention.
- Postgres: `ScenarioSessionRecord` + its repository `save()`/`_to_domain()` + the shared
  `scenario_session_to_payload`/`from_payload` all need the new field(s). Migration is
  additive/nullable, no backfill — follows the reversible `add_column`/`drop_column` shape of
  `20260722_0005_scenario_access_control.py` and `20260726_0008_session_directives.py`.
  **Current head is `20260726_0008`** (recheck at implementation time).

## Design decisions

- **Reply format**: first line (up to the first newline) is the name; everything after is the
  description. No second line → no description (still requires a non-blank first line — a
  blank/whitespace-only message is *not* auto-treated as skip; use `/skip` explicitly).
- **Skip path**: explicit `/skip` command only. Any other reply — even a single word — is taken
  as persona input (the name). This keeps the parse unambiguous: no heuristic guessing about
  whether a short reply was "meant" as a skip.
- **Abandoned prompts**: no timeout and no blocking of other commands. Running `/play` or
  `/clear` again simply re-issues the prompt against the newly created session, silently
  replacing the pending state — the old awaiting-persona session is orphaned the same way
  `restart` already orphans prior sessions today.
- **`/clear` confirms before acting.** It is the only command that destroys player-authored
  configuration, and it sits one letter away from `/continue` in the menu. `/restart` keeps
  today's no-confirmation behavior — it is now non-destructive to settings.
- **Naming**: the new use case is `PlaythroughService.clear(...)`. Note the existing
  `ChatService.clear_conversation(...)` (ADR-014) — wired to no command today, wipes only a
  transcript. Do not conflate them; if the overlap proves confusing, rename that one rather
  than the command.

## Tasks

### Domain / persistence
- [x] Add `user_persona_name: str | None` and `user_persona_description: str | None` to
      `ScenarioSession` (frozen dataclass, set once at creation or via a single narrow
      "set persona" transition — never a general update).
- [x] Alembic migration: additive nullable columns on `scenario_sessions`, reversible
      (`upgrade`/`downgrade` verified against a real DB per CLAUDE.md).
- [x] Update `ScenarioSessionRecord`, the repository's `save()`/`_to_domain()`, and
      `scenario_session_to_payload`/`from_payload` (transfer format, ADR-024) to carry the new
      fields.
- [x] Extend the `ScenarioSession` store contract test suite for the new fields.

### PlaythroughService — reset tiers (ADR-025)
- [x] `restart(...)` carries the persona forward alongside the directives it already carries
      (`playthrough_service.py::restart` → `_begin(directives=...)`; add the persona to the
      same carry-over).
- [x] New `clear(...)`: same path as `restart` but carrying **nothing** player-owned — i.e.
      `_begin(directives=None, persona=None)`. Express the two as one parameterized path, not
      two implementations.
- [x] **`clear` stamps the outgoing session as superseded**, exactly as `restart` does — see
      [S016](S016-session-soft-delete-lifecycle.md), which owns the soft-delete lifecycle and
      the session-resurrection fix (ADR-025, negative consequence 3). `/clear` is the third
      path that supersedes a session, so **S016 should land first, or in the same change**;
      building `clear` on top of the current orphan-and-hope behavior would add a third way to
      hit that bug.

### Telegram adapter — pending-persona state
- [x] New small store mirroring `TelegramNarratorStore` (e.g. `TelegramPendingPersonaStore`),
      keyed by `(owner_kind, owner_id)`: "this owner has a freshly-created session awaiting a
      persona reply."
- [x] In the `PLAY` handler, gated to `owner_kind == "user"` **and to genuinely new sessions**
      (`_begin`, not `_resume`): **do not** send `_format_start` immediately — send the persona
      prompt instead and record the pending state. Group sessions skip this entirely.
- [x] New `/clear` command: confirm, then `PlaythroughService.clear(...)`, then — for user
      sessions — issue the persona prompt exactly as a new `/play` does. Group-admin-only in
      groups, like `/restart`. Add to `SUPPORTED_COMMANDS`, `TELEGRAM_MENU_COMMANDS`, and the
      authorized help text, wording it distinctly from `/restart`.
- [x] **`/restart` no longer prompts** — it carries the persona forward and sends
      `_format_start` as it does today. (Changed from the first draft of this epic.)
- [x] At the top of `handle_message` (or wherever plain-text non-command messages are routed),
      check pending-persona state before normal chat dispatch: if set, treat this message as the
      persona reply — `/skip` → Telegram username, no description; anything else → first line as
      name, remainder as description — persist it, clear the pending state, **then** send the
      story intro (`_format_start`) as today.
- [x] A fresh `/play`/`/clear` while a persona reply is still pending simply overwrites the
      pending state to point at the new session.

### ConversationBuilder
- [x] `{{user}}` resolves to `session.user_persona_name` when set, else current fallback
      (`payload.user.display_name`).
- [x] New **User Persona** prompt section, rendered only when a description is present. Place
      it with the static context (World / Characters / User Persona / Story) — i.e. *before*
      the S014 directive block (`Language → Scenario Rules → Director Instructions`), which
      stays immediately ahead of the memory hint. Omit cleanly when absent, per S014's
      no-empty-headers rule.

## Verification
- [x] Unit tests: `ConversationBuilder` resolves `{{user}}` from the persona when set, falls back
      otherwise; User Persona section omitted when no description; reply parser splits
      name/description on first newline and handles `/skip`.
- [x] Unit tests for the reset tiers: `restart` preserves persona + language + rules and drops a
      pending director note; `clear` resets all of them; neither leaves a resurrectable
      superseded session behind.
- [x] Migration round-trip (`upgrade head` + `downgrade`) against a real DB.
- [x] Contract test covering the new session fields end to end through the Postgres store.
- [x] Live-verify over Telegram: `/play` a new scenario → prompted → reply with name+description
      → intro appears with `{{user}}` substituted correctly in the opening line; `/play` with
      `/skip` → Telegram username used, no description section rendered; **`/restart` does *not*
      re-prompt and keeps persona/language/rules**; **`/clear` confirms, then re-prompts and the
      settings are back to defaults**; resuming an existing session does not prompt; triggering
      `/clear` again while a persona reply is pending re-prompts against the new session with no
      stuck state.


## Implementation notes (2026-07-27)

Where the shipped shape differs from, or goes beyond, the plan above:

* **Persona parsing lives in the domain** (`core/scenario/user_persona.py::parse_persona_reply`),
  not the adapter: "first line is the name" is the persona's own contract, so a second
  transport would parse it identically. The adapter owns only `/skip`.
* **`{{user}}` is now resolved in the text the player reads, too.** `_resolve_templates` was
  a private builder method; the substitution moved to `core/prompts/templates.py` and the
  Telegram adapter's `_format_start` uses it, so a scenario whose `initial_context` contains
  `{{user}}` shows the persona name instead of a raw placeholder. Storage stays raw —
  templates are resolved at render time, which is what lets one stored opening render
  correctly before *and* after the persona is set.
* **`/clear` confirms via `/clear confirm`** rather than an inline keyboard: the adapter has
  no callback-query infrastructure, and a typed confirmation is unambiguous with no extra
  transport state.
* **`/restart` no longer wipes the outgoing transcript.** It previously called
  `conversation_store.clear(...)` on the old session; superseding it keeps that history
  readable by id, which is the whole reason S016 soft-deletes instead of purging. The new
  session has its own memory key, so nothing leaks between them.
* **`save()` stamps `updated_at`** (S016 option (a)) and therefore returns the stamped
  session rather than its argument; the store contract test asserts that explicitly.
* A `FakePendingPersonaStore` was added to the Telegram test fixtures — the adapter's default
  store is file-backed under `data/`, so without it the suite wrote into the real data dir.

* **Admin panel can set *and edit* a session's persona** (added after the first pass, on
  request): `PUT /admin/sessions/{id}/persona` plus a two-field form on the session detail
  page, pre-filled with what is stored. This is the **operator exception** to the set-once
  contract — recorded as an amendment to ADR-025 — implemented as a separate domain
  transition, `ScenarioSession.override_persona`, so the player-facing `with_persona` guard
  is untouched. Refuses a superseded session (409, its prompt is never built again) and a
  blank name (400). The UI confirms a *rename* specifically, because transcripts store
  `{{user}}` unresolved: past turns re-render under the new name and stop matching what the
  player read. Verified against the real dev DB: `updated_at` moved off its backfilled value
  on write, and the test write was reverted afterwards.
