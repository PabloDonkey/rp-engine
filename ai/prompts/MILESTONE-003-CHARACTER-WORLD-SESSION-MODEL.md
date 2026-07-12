# Milestone 003 — Character / World / Session Model

## Goal

Introduce the core roleplay domain entities:

* Character
* User Persona
* World
* Session

This milestone creates the foundation for persistent roleplay experiences.

After this milestone:

* A user can select a character to interact with.
* A session represents a specific roleplay relationship.
* Character and world data are independent from adapters.
* Conversation history and memory can later attach to a session.
* The engine no longer treats history as belonging directly to a Telegram user.

---

# Motivation

The previous milestone introduced provider-independent users.

The next step is separating:

```text
User
```

from:

```text
Roleplay Context
```

A person can have multiple roleplay experiences:

Example:

```text
User: Pablo

Session 1:
    Character: Belzebuth
    World: Fantasy

Session 2:
    Character: Space Captain
    World: Sci-Fi
```

These sessions must not share:

* conversation history
* memory
* character state
* world state

---

# Target Architecture

```text
User
 |
 |
 +----------------+
 |                |
 v                v

Session A       Session B

User            User
Character       Character
World           World
History         History
Memory          Memory
```

---

# Domain Structure

Create:

```text
core/
├── character/
│   ├── character.py
│   └── character_card.py
│
├── world/
│   └── world.py
│
├── session/
│   └── session.py
│
└── user/
    └── user.py
```

---

# Character Entity

A character represents the AI roleplay persona.

Example:

```python
Character
├── id
├── name
├── description
├── personality
├── greeting
└── metadata
```

Example:

```json
{
    "id": "belzebuth",
    "name": "Belzebuth",
    "description": "A dragoness companion.",
    "personality": "Warm, playful and protective."
}
```

---

## Character Identity

The character ID should be independent from display name.

Avoid:

```text
character_id = "Belzebuth"
```

Prefer:

```text
character_id = UUID
```

or a controlled slug:

```text
character_id = "belzebuth"
```

Characters are application-owned data, not external identities.

---

# Character Card

Character information should be separated from runtime state.

Example:

```text
characters/
└── belzebuth/
    ├── card.json
    ├── lore.md
    └── state.json
```

## Static Data

`card.json`

Contains:

* name
* description
* personality
* speaking style
* background

## Runtime State

`state.json`

Contains:

* current mood
* relationship status
* temporary changes

This separation prevents the character definition from being corrupted by a session.

---

# User Persona

A user can also have a roleplay persona.

Important distinction:

```text
User
```

is the real engine user.

```text
User Persona
```

is the identity used inside roleplay.

Example:

Real user:

```text
User:
    id = UUID
```

Roleplay persona:

```text
Persona:
    name = Pablo
    description = Anthro donkey adventurer
```

Create later if needed:

```text
user/
└── personas/
```

For this milestone, keep the concept ready but do not over-implement.

---

# World Entity

A world represents the environment where the roleplay happens.

Example:

```python
World
├── id
├── name
├── description
├── rules
└── metadata
```

Example:

```json
{
    "id": "fantasy",
    "name": "Fantasy Realm",
    "description": "A medieval magical world.",
    "rules": [
        "Magic exists",
        "Dragons are intelligent"
    ]
}
```

---

# Session Entity

The session is the central roleplay container.

A session connects:

```text
User
Character
World
```

Example:

```python
Session
├── id
├── user_id
├── character_id
├── world_id
├── created_at
└── metadata
```

Future milestones will add:

* conversation history
* memory
* character state
* world state

---

# Session Storage

Target structure:

```text
data/
├── users/
│
├── characters/
│
├── worlds/
│
└── sessions/
    └── <session_id>/
        └── session.json
```

Example:

```json
{
    "id": "session_uuid",
    "user_id": "user_uuid",
    "character_id": "belzebuth",
    "world_id": "fantasy"
}
```

---

# Commands

Introduce application commands.

Telegram adapter can expose:

```text
/character Belzebuth
```

Meaning:

Select or create the active character.

Not:

"Change a string."

---

Application command:

```python
SelectCharacterCommand(
    character_name="Belzebuth"
)
```

Flow:

```text
Telegram
    |
    v
Command
    |
    v
CharacterService
    |
    v
Session Update
```

---

# Session Selection Rules

When selecting a character:

```text
Existing session?
        |
        +-- Yes --> Load session
        |
        +-- No --> Create session
```

Example:

User:

```text
Pablo
```

Selects:

```text
Belzebuth
```

System checks:

```text
Pablo + Belzebuth + Current World
```

If no session exists:

Create one.

---

# Constraints

* Domain must not know Telegram exists.
* Character IDs must not depend on usernames.
* World data must not be stored inside characters.
* Character definition and runtime state must be separate.
* Sessions own roleplay relationships.
* Do not add conversation history yet.

---

# Tests

## Character

Verify:

* Character loads correctly.
* Static data and runtime state are separated.

## World

Verify:

* World data can load independently.

## Session

Verify:

* Session references valid user, character and world.
* Multiple sessions can exist for one user.

Example:

```text
User A
 |
 +-- Session 1
 |       Character A
 |
 +-- Session 2
         Character B
```

## Character Switching

Verify:

```text
/character Alice
```

does not overwrite:

```text
Alice
```

with:

```text
Belzebuth
```

---

# Documentation Updates

Update:

* `DOMAIN_MODEL.md`
* `ARCHITECTURE.md`
* `ROADMAP.md`

Document:

* User owns sessions.
* Sessions own roleplay context.
* Characters and worlds are reusable assets.

---

# Success Criteria

This milestone is complete when:

* Users can have multiple sessions.
* Sessions reference characters and worlds.
* Characters are independent reusable entities.
* Worlds are independent reusable entities.
* Telegram only acts as an adapter.
* The engine has enough domain structure to build conversations in the next milestone.
