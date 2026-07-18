# Character Card v3 Adoption + Telegram Character Creation Commands

## Goal

Adopt Character Card Specification v3 as the canonical character definition format.

Use the specification as the source of truth for:

- character card structure
- required fields
- validation rules
- field constraints

Add Telegram commands that allow users to create and modify their own characters without manually editing JSON.

---

# Documentation Integration

First, add the Character Card v3 specification to project documentation.

Tasks:

- Add SPEC_V3.md to the documentation folder.
- Reference it from:
  - DOMAIN_MODEL.md
  - ARCHITECTURE.md
  - DECISIONS.md
  - README.md where relevant

Document that:

Character Card v3 represents the portable Character Definition format.

It contains:

- name
- description
- personality
- scenario
- first message
- additional optional metadata

The RP Engine maps the external character card format into its internal Character domain model.

---

# Architecture Decision Record

Create a new ADR.

Suggested:

ADR-022 — Adopt Character Card Specification v3

Document:

## Context

The engine requires a portable character definition format.

A custom format would duplicate existing ecosystem work.

## Decision

Adopt Character Card Specification v3 as the external character definition contract.

The Character Card represents:

- identity
- personality
- scenario
- behavior rules
- initial greeting

Engine-specific information remains outside the card:

- owner_id
- visibility
- database identifiers
- memories
- sessions
- runtime metadata

## Consequences

Benefits:

- compatibility with existing character ecosystems
- simpler import/export
- less custom schema maintenance

Tradeoffs:

- internal model requires mapping layer
- future spec versions require migration handling

---

# Character Creation UX

Add Telegram commands for users to create and modify their own characters.

The commands should update the Character Card.

Required creation fields:

1. Name
2. Description
3. Personality
4. Scenario
5. First message

The user should be able to:

- create a character
- edit their own characters
- view current values
- validate before saving

---

# Telegram Commands

Design commands following existing adapter architecture.

Do not put character card logic inside Telegram adapter.

Telegram adapter should only:

- parse commands
- collect user input
- call application services
- display results

Character validation and updates belong in application/domain layers.

---

Suggested commands:

## /character create

Starts character creation flow.

Example:

User:

/character create


Bot:

What is the character name?


Then collect:

1. name
2. description
3. personality
4. scenario
5. first_message

After completion:

- validate against SPEC_V3.md
- create Character Definition
- assign owner_id
- default visibility PRIVATE
- save through CharacterStore

---

## /character edit

Allows owner modification.

Example:


/character edit Belzebuth


Show editable fields:

Name
Description
Personality
Scenario
First message

After modification:

- validate Character Card
- save updated definition

---

## /character show

Displays current character card summary.

---

## /character validate

Runs SPEC_V3 validation and reports errors.

---

# Validation

Implement validation based on SPEC_V3.md.

Validation must happen:

- before creation
- before updates
- during import/export

Validation errors should be user-friendly.

Example:

Instead of:


field.description missing


Show:


Your character needs a description.
Please add one with:
/character edit description


---

# Domain Model

Keep the current separation:

Character Definition:

- Character Card v3 data
- owner_id
- visibility

Character Memory:

- separate system
- not part of the card

Session:

- conversation context

Do not introduce Character State.

---

# Persistence

No new persistence backend should be created.

Reuse existing CharacterStore.

Ensure:

JSON backend:
- stores Character Card data correctly

PostgreSQL backend:
- stores Character Definition correctly

Both must preserve the Character Card representation.

---

# Tests

Add tests for:

Application layer:

- create character from card data
- update owned character
- reject editing another user's private character
- validate required fields

Repository:

- character card fields survive save/load

Adapter:

- Telegram command flow

Validation:

- valid card accepted
- invalid card rejected with useful errors

---

# Documentation

Update:

- COMMANDS.md
- ARCHITECTURE.md
- DOMAIN_MODEL.md
- DECISIONS.md
- README.md

Document:

- Character Card v3 as the character creation format
- Telegram character workflow
- ownership rules
- validation behavior

---

# Constraints

Maintain clean architecture.

Do not:
- put SPEC_V3 validation inside Telegram code
- store memories inside Character Cards
- store session data inside Character Cards
- introduce Character State

The final architecture should be:

Character Card
        |
        ▼
Character Definition
        |
        ├── Owner
        ├── Visibility
        └── Memories (separate)

Session
        |
        └── Conversation