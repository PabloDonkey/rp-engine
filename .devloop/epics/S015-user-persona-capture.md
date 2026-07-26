# S015 · User persona capture on new session start

**Status:** 🔵 Backlog (shares prompt-layout work with [S014](S014-session-directives.md);
introduces the "User Persona" section from that epic's design notes)
**Effort:** ~1-2 days
**Risk:** Medium — new pending-input mechanism in the Telegram adapter (nothing like it exists
today), a new immutable persisted field + Alembic migration, and a `{{user}}` resolution change.
**Design decisions:** locked in below (reply format, `/skip`, abandoned-prompt handling) —
ready for implementation, no open questions remaining.

## Context

When `/play <id>` starts a **brand-new** session, or `/restart` recreates one (both go through
`PlaythroughService._begin`, `application/services/playthrough_service.py:143-180`), the bot
should ask the player to define their character before the story intro is shown:

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
later if group personas are wanted.

### Why this needs new plumbing

Confirmed via exploration (`Explore` agent, see prior turn) that:
- The Telegram adapter is currently **fully stateless per message** — `handle_message` parses
  and dispatches a single update with no cross-message memory. The one precedent for small
  transport-local state is `TelegramNarratorStore`
  (`src/rp_engine/adapters/telegram/narrator_store.py`) — a tiny per-chat file-backed
  get/set/clear store used by `/retry`. A "waiting for persona reply" store should follow the
  exact same shape, keyed by `(owner_kind, owner_id)` like every other session-scoped lookup.
- `{{user}}` is resolved in `ConversationBuilder._resolve_templates`
  (`core/conversation/builder.py:332-346`) as `payload.user.display_name`, unconditionally —
  no per-session override exists. `payload.user` comes from `ChatService._load_scenario_context`
  (`application/services/chat_service.py:365-402`), which for **group** sessions synthesizes a
  `User` from the `Group` — i.e. today a group's `{{user}}` is the group's name, not any one
  player's. A per-`ScenarioSession` persona field (not a `User`-level field) is therefore the
  right place to hook in, and resolves uniformly for both `owner_kind`s.
- `ScenarioSession` (`core/scenario/scenario_session.py:9-77`) is a frozen dataclass with no
  persona field today; `metadata: dict[str, str]` exists but is used for ephemeral continuity
  state, not schema-visible identity — a first-class nullable column matches how prior fields
  (e.g. `visibility` on `ScenarioDefinition`) were added, and keeps the "immutable once set"
  contract enforceable in the type rather than a convention on a string bag.
- Postgres: `ScenarioSessionRecord` (`infrastructure/postgres/models.py:72-99`) + its repository
  `save()`/`_to_domain()` (`infrastructure/postgres/repositories/scenario_session_store.py`) +
  the shared `scenario_session_to_payload`/`from_payload` (`infrastructure/scenario_serialization.py:148-175`)
  all need the new field(s). Migration is additive/nullable, no backfill — follows the reversible
  shape of `alembic/versions/20260722_0005_scenario_access_control.py` (`add_column` /
  `drop_column` pair), chained after the current head (`20260723_0007_identity_trace_tables.py`
  — recheck head at implementation time, S013/S014 may have added more since).

## Design decisions

- **Reply format**: first line (up to the first newline) is the name; everything after is the
  description. No second line → no description (still requires a non-blank first line — a
  blank/whitespace-only message is *not* auto-treated as skip; use `/skip` explicitly).
- **Skip path**: explicit `/skip` command only. Any other reply — even a single word — is taken
  as persona input (the name). This keeps the parse unambiguous: no heuristic guessing about
  whether a short reply was "meant" as a skip.
- **Abandoned prompts**: no timeout and no blocking of other commands. Running `/play` or
  `/restart` again simply re-issues the prompt against the newly created session, silently
  replacing the pending state — the old awaiting-persona session is orphaned the same way
  `restart` already orphans prior sessions today (`PlaythroughService.restart`,
  `playthrough_service.py:95-110`).

## Tasks

### Domain / persistence
- [ ] Add `user_persona_name: str | None` and `user_persona_description: str | None` to
      `ScenarioSession` (frozen dataclass, set once at creation or via a single narrow
      "set persona" transition — never a general update).
- [ ] Alembic migration: additive nullable columns on `scenario_sessions`, reversible
      (`upgrade`/`downgrade` verified against a real DB per CLAUDE.md).
- [ ] Update `ScenarioSessionRecord`, the repository's `save()`/`_to_domain()`, and
      `scenario_session_to_payload`/`from_payload` (transfer format, ADR-024) to carry the new
      fields.
- [ ] Extend the `ScenarioSession` store contract test suite for the new fields.

### Telegram adapter — pending-persona state
- [ ] New small store mirroring `TelegramNarratorStore` (e.g. `TelegramPendingPersonaStore`),
      keyed by `(owner_kind, owner_id)`: "this owner has a freshly-created session awaiting a
      persona reply."
- [ ] In the `PLAY`/`RESTART` handlers (`adapter.py:269-296`, `315-328`), gated to
      `owner_kind == "user"` only, after `_begin` creates the new session: **do not** send
      `_format_start` immediately — send the persona prompt instead and record the pending
      state. Group sessions (`owner_kind == "group"`) skip this entirely and behave as today.
- [ ] At the top of `handle_message` (or wherever plain-text non-command messages are routed),
      check pending-persona state before normal chat dispatch: if set, treat this message as the
      persona reply — `/skip` → Telegram username, no description; anything else → first line as
      name, remainder as description — persist it, clear the pending state, **then** send the
      story intro (`_format_start`) as today.
- [ ] A fresh `/play`/`/restart` while a persona reply is still pending simply overwrites the
      pending state to point at the new session (no explicit cleanup needed — matches how
      `restart` already orphans the previous session).

### ConversationBuilder
- [ ] `{{user}}` resolves to `session.user_persona_name` when set, else current fallback
      (`payload.user.display_name`).
- [ ] New **User Persona** prompt section (per S014's recommended layout, placed with the static
      context — World/Characters/User Persona/Story), rendered only when a description is
      present.

## Verification
- [ ] Unit tests: `ConversationBuilder` resolves `{{user}}` from the persona when set, falls back
      otherwise; User Persona section omitted when no description; reply parser splits
      name/description on first newline and handles `/skip`.
- [ ] Migration round-trip (`upgrade head` + `downgrade`) against a real DB.
- [ ] Contract test covering the new session fields end to end through the Postgres store.
- [ ] Live-verify over Telegram: `/play` a new scenario → prompted → reply with name+description
      → intro appears with `{{user}}` substituted correctly in the opening line; `/play`/`/restart`
      with `/skip` → Telegram username used, no description section rendered; `/restart` also
      re-prompts; resuming an existing session does not; triggering `/restart` again while a
      persona reply is pending re-prompts against the new session with no stuck state.
