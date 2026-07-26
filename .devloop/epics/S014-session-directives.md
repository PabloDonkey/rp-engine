# S014 · Session directives — Director Mode, Scenario Rules, Language preference

**Status:** 🔵 Backlog
**Effort:** ~2-3 days (three related features sharing one mechanism)
**Risk:** Medium (touches `ConversationBuilder` prompt layout + session metadata + Telegram
command surface)

## Context

Three new user-facing controls that all work the same way — a Telegram command writes into
session metadata, `ConversationBuilder` injects a dedicated system-prompt section from it —
but differ in persistence/lifetime:

| Feature | Command(s) | Lifetime | Prompt section |
|---|---|---|---|
| Director Mode | `/director <instruction>` | one-turn (auto-cleared after generation) | Director Instructions |
| Persistent Scenario Rules | `/rule add <instruction>`, `/rules`, `/rule remove <id>` | persistent per session until removed | Scenario Rules |
| Language preference | `/language <code>` (`en`, `fr`, `auto`) | persistent per session | Language |

Bundled as one epic because they share the same plumbing (session metadata field +
`ConversationBuilder` section + Telegram command parsing) and the recommended system-prompt
layout interleaves them:

```
Role → World → Characters → Story → Roleplay Rules
  → Language → Scenario Rules → Director Instructions → Memory
  → Current Scene → Recent Conversation
```

Rationale for the ordering: permanent identity/behavior first, then persistent user
preferences (language, scenario rules), then the highest-priority-but-temporary Director
instruction, then dynamic context (memory, scene, history) last. Director instructions are
out-of-character/invisible to the roleplay — the model should integrate them without
mentioning them.

A **User Persona** section (the player's predefined identity, when captured) is scoped
entirely to [S015](S015-user-persona-capture.md) — that epic owns its placement in the layout,
its own prompt-section rendering, and `{{user}}` resolution.

## Tasks

### Domain / session metadata
- [ ] Add to session/scenario-session metadata: `language` (persistent, default e.g. `auto`),
      `scenario_rules` (persistent list, each with a stable removable id), `director_instruction`
      (transient, cleared immediately after the next generation completes).
- [ ] Decide storage shape (embedded JSON metadata vs. dedicated columns) consistent with
      existing `ScenarioSession` persistence (Postgres-only, ADR-024).

### ConversationBuilder
- [ ] Extend prompt layout with the three new sections in the order above; omit a section
      cleanly when empty (no empty headers in the rendered prompt).
- [ ] Director instruction is read-and-cleared as part of the turn that consumes it (needs to
      happen post-generation, likely in `ChatService`/`RPOrchestrator`, not just the builder).

### Telegram adapter
- [ ] `/director <instruction>` — sets the transient field for the next turn only.
- [ ] `/rule add <instruction>` / `/rules` (list with ids) / `/rule remove <id>` — CRUD on the
      persistent list.
- [ ] `/language <code>` — validates against a small allowed set (`en`, `fr`, `auto`, …).
- [ ] Confirm each command's authorization/invocation policy matches existing scenario-session
      commands (owner-only, per `docs/ARCHITECTURE.md`).

### Admin panel (optional follow-up, not required for MVP)
- [ ] Surface `language` / `scenario_rules` / last `director_instruction` on the session detail
      view (read-only) alongside S009's transcript view.

## Verification
- [ ] Unit tests: `ConversationBuilder` renders/omits each section correctly; director
      instruction clears after one turn.
- [ ] Contract/integration test for the metadata round-trip through the Postgres session store.
- [ ] Live-verify over Telegram: set a rule, confirm it persists across turns; issue a director
      instruction, confirm it applies once then disappears from the next prompt; switch language
      and confirm responses follow.
