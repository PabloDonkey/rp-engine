# Scenario Authoring Guide

RP Engine is scenario-driven: players pick an adventure from a **curated library** and
play it. Scenarios are authored by the developer as JSON files — no code change or deploy
is required to add or edit one.

This document describes the catalog, the JSON format, and how a scenario becomes a
playthrough at runtime.

---

## The catalog

Curated scenarios live as `*.json` files in the catalog directory:

* Default: `data/catalog/`
* Configurable: `RP_ENGINE_SCENARIO_CATALOG_DIR`

At startup the engine loads every `*.json` file in that directory into a read-only
`ScenarioCatalog`. Files that are missing required fields or are not valid JSON are
skipped (with a warning) — one bad file never breaks the rest of the library.

`/scenarios` lists the catalog (sorted by name). `/play <id>` looks a scenario up by its
`id` and starts a playthrough.

---

## Scenario JSON format

A scenario file is a single JSON object. It maps directly onto the `ScenarioDefinition`
domain model (see `DOMAIN_MODEL.md`).

| Field             | Type                     | Required | Notes |
| ----------------- | ------------------------ | -------- | ----- |
| `id`              | string                   | yes      | Stable catalog id used by `/play <id>`. Keep it URL/slug-friendly. |
| `owner_id`        | UUID string              | yes      | Curated scenarios use the system owner `00000000-0000-0000-0000-000000000000`. |
| `name`            | string                   | yes      | Display name shown by `/scenarios`. |
| `description`     | string                   | yes      | One-line pitch shown by `/scenarios`. May be empty. |
| `world`           | object or `null`         | no       | The environment. See **World** below. |
| `role_profiles`   | object (role → profile)  | no       | Abstract roles; optional, reserved for richer casts. |
| `characters`      | object (role → character)| no       | Concrete characters keyed by role. A narration-style scenario typically has one `narrator`. |
| `rules`           | array of strings         | no       | Scenario-specific instructions injected into the system prompt. |
| `story_graph`     | object or `null`         | no       | Optional narrative structure (inert data; see `DOMAIN_MODEL.md`). |
| `initial_context` | string                   | no       | The opening narration. Sent to the player when the playthrough starts. |
| `metadata`        | object (string → string) | no       | Free-form tags (e.g. `{"genre": "heist"}`). |

Omitted optional fields default to empty (`{}` / `[]` / `null` / `""`).

### World

```json
"world": {
  "id": "eldoria",
  "name": "Eldoria",
  "description": "A crumbling fantasy city where old magic still lingers.",
  "rules": ["Magic is rare and feared."],
  "metadata": {}
}
```

### Character

Characters are keyed by a **role** (e.g. `"narrator"`, `"protagonist"`). The engine uses
the active character to build the prompt and to resolve `{{char}}`.

```json
"characters": {
  "narrator": {
    "id": "narrator-sealed-vault",
    "owner_id": "00000000-0000-0000-0000-000000000000",
    "visibility": "PUBLIC",
    "name": "Narrator",
    "description": "An omniscient guide voicing the world.",
    "personality": "Atmospheric and terse.",
    "greeting": "",
    "metadata": {}
  }
}
```

A scenario with no `characters` is **characterless** (freeform): the prompt is built from
the world and rules only, and `{{char}}` resolves to "the character".

### Templates

Text fields may use these placeholders, resolved at prompt-build time:

* `{{user}}` — the player's display name
* `{{char}}` — the active character's name
* `{{world}}` — the world's name

---

## Full example

`data/catalog/sealed-vault.json`:

```json
{
  "id": "sealed-vault",
  "owner_id": "00000000-0000-0000-0000-000000000000",
  "name": "The Sealed Vault",
  "description": "A tense heist beneath the old city.",
  "world": {
    "id": "eldoria",
    "name": "Eldoria",
    "description": "A crumbling fantasy city where old magic still lingers in the stone.",
    "rules": ["Magic is rare and feared.", "The city guard is never far."],
    "metadata": {}
  },
  "role_profiles": {},
  "characters": {
    "narrator": {
      "id": "narrator-sealed-vault",
      "owner_id": "00000000-0000-0000-0000-000000000000",
      "visibility": "PUBLIC",
      "name": "Narrator",
      "description": "An omniscient guide voicing the world and everyone in it.",
      "personality": "Atmospheric and terse. Describes only what {{user}} can perceive.",
      "greeting": "",
      "metadata": {}
    }
  },
  "rules": [
    "Address the player in the second person.",
    "Keep each reply to a few vivid sentences.",
    "End on a beat that invites the player to act."
  ],
  "story_graph": null,
  "initial_context": "You crouch before the sealed vault door, its runes still faintly glowing.",
  "metadata": { "genre": "heist" }
}
```

---

## From scenario to playthrough

When a player runs `/play sealed-vault`:

1. The catalog is looked up by `id`.
2. The scenario definition is persisted (so the chat engine can load it at reply time).
3. A per-player `ScenarioSession` is created and set active for that owner (user or group).
4. The `initial_context` (or, if empty, a character greeting) is seeded as the opening
   narrator turn and sent to the player.

From then on, the player advances the story with plain messages (or `/chat` in groups),
and `/continue`, `/retry`, `/restart` operate on that active playthrough. See the Telegram
Commands section of the `README.md` for the full command reference.

Multiple players (and groups) can play the same scenario independently — the curated
definition is a shared blueprint, but every playthrough has its own session and history.

---

## Tips

* Keep `id` stable once players may have sessions referencing it.
* Prefer short, directive `rules` — they are injected verbatim into the system prompt.
* Use `initial_context` to set the scene in the second person; it is the first thing the
  player sees.
* Editing a catalog file and restarting the engine updates the blueprint; existing
  playthroughs pick up the new definition on their next reply.
