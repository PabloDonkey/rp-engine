# Task: Resolve Conversation Identity Model Drift

We need to resolve the documentation/code drift around conversation identity.

Before making changes, inspect:

- ARCHITECTURE.md
- DOMAIN_MODEL.md
- DECISIONS.md
- SPEC.md
- Current conversation/session/user related code
- Existing tests

The current problem:

Documentation describes:
- Private Telegram chats map to user identity memory
- Group Telegram chats map to group identity memory

But implementation currently enforces:
- Conversations are session-scoped
- Both private and group flows resolve through session identity

We need to choose and implement the canonical model.

## Decision to implement

Adopt this model:

A Conversation belongs to a Session.

A Session represents an RP context.

A Session belongs to an owner context:
- User session: owned by a User
- Group session: owned by a Group context

External platform identities (Telegram IDs) are adapter concerns only.

The core/domain must not depend on Telegram concepts.

Conceptual model:

User
 |
 +-- Sessions
       |
       +-- Conversations
             |
             +-- Messages


Telegram User ID:
    maps to UserIdentity
    maps to User

Telegram Group ID:
    maps to GroupIdentity
    maps to Group


The engine should reason about:
- User
- Group
- Session
- Conversation

It should not reason about:
- Telegram user IDs
- Telegram chat IDs
- Telegram message IDs


## Required changes

### 1. Domain model

Review current models.

Ensure the domain clearly represents:

- User
- External Identity
- Group (if already needed)
- Session ownership
- Conversation scope

Do not introduce Telegram-specific fields into domain entities.

If a required entity is missing, add it.

Update:
- DOMAIN_MODEL.md

---

### 2. Architecture documentation

Update ARCHITECTURE.md:

Clarify:

- adapters translate external identities into domain identities
- sessions are the RP context boundary
- conversations are children of sessions
- memory lookup happens through session ownership

Remove any wording implying:
"Telegram private chat == memory identity"

unless it is explicitly described as an adapter mapping.

---

### 3. Decision records

Update DECISIONS.md.

Fix ADR traceability by resolving duplicate ADR-011, renumber if necessary

Create a new ADR:

ADR-0XX (n+1) — Conversation Ownership and Identity Scope

The ADR should explain:

Context:
- Previous design mixed platform identity and RP identity.

Decision:
- Sessions are the canonical RP context.
- Conversations belong to sessions.
- External identities are mapped by adapters.

Consequences:
- Multiple sessions per user are supported.
- Same character can have different states in different sessions.
- Future adapters (Discord/web/local) do not affect the domain model.

Mark any conflicting ADR as superseded.

Do not delete old ADR history.

---

### 4. Code review

Inspect the implementation.

Do NOT rewrite unrelated systems.

Only modify code if needed to make it consistent with the chosen model.

Check:

- identity resolution
- session creation
- conversation creation
- memory keys
- Telegram adapter mapping

The adapter should perform:

Telegram identity
        |
        v
Domain identity
        |
        v
Session lookup/creation


The core should never parse Telegram IDs.

---

### 5. Tests

Update/add tests proving:

Private flow:

Telegram user A
 -> resolves User A
 -> creates/uses Session A


Group flow:

Telegram group X
 -> resolves Group X
 -> creates/uses Group Session X


Different users cannot access each other's sessions.

Different groups do not share conversation state.

---

## Constraints

Do not:
- redesign memory
- refactor unrelated code

This task is only about making the identity/session model coherent.

After changes, provide:

1. Summary of code changes
2. Documentation changes
3. New ADR number
4. Remaining known limitations