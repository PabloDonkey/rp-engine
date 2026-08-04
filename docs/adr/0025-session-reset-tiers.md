---
id: ADR-025
title: "Session Reset Tiers: `/restart` Preserves Player Settings, `/clear` Resets Them"
status: accepted
created: 2026-07-27
supersedes: []
superseded_by: []
---

# ADR-025 — Session Reset Tiers: `/restart` Preserves Player Settings, `/clear` Resets Them

**Implemented:** 2026-07-27 (S015; the soft-delete half is S016)

## Context

Until S014 a `ScenarioSession` held only story state — participants, world state, story
progress, transcript. Resetting it was unambiguous: everything on it came from the story,
so restarting the story reset all of it.

S014 introduced the first **player-owned** session state: `SessionDirectives` (language,
scenario rules, and a one-turn director instruction). S015 will add a second, the user
persona. That changes what `/restart` means, because both readings are now defensible:

* Reset everything — a player who restarts a scene to try a different approach silently
  loses the language they chose and the rules they wrote. Settings feel fragile, and the
  most common reason to restart is the one that punishes you.
* Reset nothing player-owned — but S015's persona is deliberately **immutable once set**
  (no edit command, to stop name drift mid-story). With no hard-reset path anywhere, a
  typo in a persona name is permanent for the life of that session.

S014 shipped the first reading's opposite (restart carries language and rules forward) as
an implementation judgement call. This ADR makes that a stated rule and supplies the
escape hatch the second bullet needs, before S015 depends on it.

There is currently no `/clear`-like command. `ChatService.clear_conversation(...)` exists
in the application API (listed in ADR-014) but is wired to no transport command and only
wipes a transcript — it is not the reset described here.

## Decision

Session resets come in two tiers, distinguished by whether **player-owned** state survives.

| | conversation history | world/story state | player-owned settings |
|---|---|---|---|
| `/restart` | reset | reset | **preserved** |
| `/clear` | reset | reset | **reset to defaults** |

* **`/restart` — story reset.** Wipes the conversation and begins the scenario again from
  its opening. Language, scenario rules, and (per S015) the user persona carry into the new
  session. A pending one-turn director instruction is dropped: it was aimed at a reply that
  will now never happen.
* **`/clear` — full reset.** Everything `/restart` does, plus player-owned settings return
  to defaults. Under S015 this re-issues the persona prompt, and is **the only way a player
  can change a persona**. It restarts the same scenario, it does not drop the player to "no
  active playthrough". (An operator can also edit a persona directly from the admin panel —
  see *Amendment* below.)
* **`/play <id>` is unchanged.** A genuinely new session starts with defaults (and prompts
  for a persona); resuming an existing one resets nothing.

**The rule for future per-session fields:** anything the *player* chose about how the story
is told survives `/restart` and is reset by `/clear`. Anything the *story* produced is reset
by both. Every new per-session field must state which side it falls on.

This is a parameter, not a branch: `restart` and `clear` share `PlaythroughService._begin`
and differ only in whether player-owned state is carried over.

## Alternatives

* **One `/restart` that resets everything** — rejected: makes player settings fragile for
  the most common reason to restart, and inverts what S014 already shipped.
* **One `/restart` that preserves everything, no `/clear`** — rejected: leaves
  deliberately-immutable settings unchangeable for the life of a session. The bounded escape
  hatch is precisely what makes a set-once persona acceptable.
* **A per-setting edit command instead (`/persona edit`, …)** — rejected for the persona: an
  edit command contradicts S015's set-once contract and reopens mid-story name drift.
  `/clear` keeps the contract while bounding the blast radius to a fresh session. Language
  and rules already have per-setting resets (`/language auto`, `/rule remove`); `/clear` is
  the bulk path, not their replacement.

## Amendment — 2026-07-27: admin-panel persona editing

The set-once contract is a **player-facing** rule, and the reasoning behind it is about the
player's experience: they must not be able to rewrite, mid-story, a name the story has
already used. It was never a claim that the value is physically unchangeable.

The admin panel may therefore set **or replace** a session's persona
(`PUT /admin/sessions/{id}/persona`). This is expressed as a separate domain transition —
`ScenarioSession.override_persona` — so `with_persona`'s guard keeps protecting every path a
player can reach; the player-facing contract above is unchanged, and `/clear` remains their
only way to change a persona.

Two things follow, and the panel surfaces both:

* Renaming changes how **past turns render**. Transcripts store `{{user}}` unresolved and
  resolve it at render time, so history stays internally consistent but stops matching what
  the player originally read. The panel confirms before a rename for exactly this reason.
* A **superseded** session is refused (409). Its prompt is never built again, so editing it
  would be a silent no-op.

## Rationale

* Restarting a scene stays cheap, which is what makes players willing to do it.
* Immutable-once-set settings become viable, because the escape hatch is bounded and
  explicit rather than a general edit surface.
* Gives every future per-session field a decision to inherit instead of re-litigating.

## Consequences

### Positive

* `/restart` is non-destructive to configuration; the distinction is learnable in one line
  of `/help`.
* Unblocks S015's set-once persona contract.
* One shared code path (`_begin` + a carry-over parameter), not two reset implementations.

### Negative

* Two similar destructive commands. The adapter must word them distinctly, and `/clear`
  should confirm before acting.
* `/clear` overlaps in name with `ChatService.clear_conversation(...)` (ADR-014), which
  wipes only a transcript. The new use case is `PlaythroughService`-level; the naming needs
  disambiguating at implementation time so the two are not mistaken for each other.
* Both `/restart` and `/clear` orphan the previous session row rather than deleting it, and
  `ScenarioSessionStore.find_by_definition` selects with no `ORDER BY` — with multiple rows
  per (owner, definition) a later `/play <same-id>` can resurrect a pre-reset session and its
  old transcript. This is pre-existing (S014 did not introduce it), but a third reset path
  makes it more likely to be hit. Tracked as **S016**, which resolves it by soft-deleting the
  superseded session (`deleted_at IS NULL` becomes the definition of "the current session")
  rather than orphaning or purging it — keeping superseded playthroughs readable for debugging
  and analysis. S016 should land before or with `/clear`.

  **Resolved 2026-07-27**, alongside `/clear`: `ScenarioSession` gained `updated_at` and
  `deleted_at` (migration `20260727_0009`), both resets stamp the outgoing session, and
  `find_by_definition` / `get_active_for_owner` / `find_by_owner` filter on
  `deleted_at IS NULL`. A consequence worth stating: `/restart` no longer wipes the outgoing
  session's transcript — superseding it keeps that history readable by id, which is the
  point. What remains of S016 is the admin panel's presentation of superseded sessions.
