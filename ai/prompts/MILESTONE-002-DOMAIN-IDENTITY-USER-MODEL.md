# Milestone 002 — Domain Identity & User Model

## Goal

Remove Telegram-specific identity handling from the core engine.

The engine currently uses Telegram IDs as user identifiers. This creates coupling between the roleplay engine and the Telegram adapter.

This milestone introduces a domain-level `User` entity with provider-independent identities.

After this milestone:

* The engine identifies users using internal collision-resistant IDs.
* Telegram IDs become adapter metadata only.
* The Telegram adapter resolves external identities into engine users.
* Existing history can be migrated from Telegram-based storage.

---

# Current Architecture Problem

Current:

```
Telegram Adapter
        |
        v
telegram_user_id
        |
        v
History / Memory
```

Problem:

* The domain knows about Telegram.
* A future Discord/Web/API adapter would require changes.
* User identity is controlled by an external platform.

---

# Target Architecture

```
Telegram
    |
    v
Telegram Identity
    |
    v
User
    |
    v
Engine
```

The engine owns the user.

Adapters only provide external identities.

---

# Domain Model

## User Entity

Create:

```
core/
└── user/
    ├── user.py
    └── identity.py
```

The user has an internal stable ID.

Example:

```python
User
├── id: UUID
├── display_name
└── identities
```

Requirements:

* `id` must be collision resistant.
* `id` must not depend on any external provider.
* `display_name` is user-facing and can change.
* Identity mapping belongs to the user.

Recommended implementation:

```python
from uuid import UUID

class User:
    id: UUID
    display_name: str
```

---

# Identity Entity

External platforms are represented as identities.

Example:

```python
Identity
├── provider
├── external_id
└── metadata
```

Example Telegram identity:

```json
{
    "provider": "telegram",
    "external_id": "123456789",
    "metadata": {
        "username": "pablodonkey",
        "first_name": "Pablo",
        "last_name": "Example"
    }
}
```

The engine must not use:

* telegram_id
* telegram_username
* discord_id
* email

as its internal user identifier.

---

# Storage Changes

## Before

Current structure:

```
data/
└── history/
    └── telegram_user_id.json
```

Example:

```
data/history/123456789.json
```

---

## After

Introduce:

```
data/
├── users/
│   └── <user_uuid>/
│       ├── profile.json
│       └── identities.json
│
└── adapters/
    └── telegram/
        └── identity_index.json
```

Example:

`profile.json`

```json
{
    "id": "8f4e2d2c-6f0e-4f31-8c2e-6d9a8a3c2b91",
    "display_name": "Pablo"
}
```

`identities.json`

```json
{
    "telegram": {
        "external_id": "123456789",
        "username": "pablodonkey",
        "first_name": "Pablo"
    }
}
```

---

# Adapter Responsibility

The Telegram adapter owns identity resolution.

Flow:

```
Telegram Update
        |
        v
telegram_user_id
        |
        v
Identity Resolver
        |
        v
User
        |
        v
ChatService
```

The application layer receives:

```python
User
```

not:

```python
telegram_id
```

---

# Identity Resolution

Create an application service responsible for resolving identities.

Example:

```python
resolve_identity(
    provider="telegram",
    external_id="123456789"
) -> User
```

Behavior:

```
Identity exists?
        |
        +-- Yes --> Return existing User
        |
        +-- No --> Create User + Identity
```

---

# Migration

Create:

```
scripts/
└── migrate_telegram_history.py
```

Responsibilities:

1. Read existing Telegram-based history.
2. Generate a new internal user UUID.
3. Create a User profile.
4. Create Telegram identity mapping.
5. Associate existing history with the new user.

Example:

Before:

```
history/
└── 123456789.json
```

After:

```
users/
└── 8f4e2d2c-6f0e-4f31-8c2e-6d9a8a3c2b91/

sessions/
└── migrated-session/
```

---

# Constraints

* No Telegram imports in the domain layer.
* No Telegram IDs stored as primary identifiers.
* No business logic based on usernames.
* User IDs must be generated internally.
* Keep adapter-specific data inside adapter/infrastructure layers.

---

# Tests

Add tests for:

## User creation

Verify:

* New users receive unique IDs.
* IDs are stable after reload.

## Identity resolution

Verify:

* Existing identity returns existing user.
* Unknown identity creates a new user.

## Adapter isolation

Verify:

* Core user model works without Telegram dependencies.

## Migration

Verify:

* Old Telegram history converts correctly.
* Existing conversations are not lost.

---

# Documentation Updates

Update:

* `ARCHITECTURE.md`
* `DOMAIN_MODEL.md`
* `DECISIONS.md`

Add an architectural decision:

## Internal User Identity

The engine uses internal collision-resistant IDs for users.

External platform identifiers are stored only as linked identities owned by adapters.

---

# Success Criteria

This milestone is complete when:

* The engine no longer depends on Telegram IDs.
* Users have internal stable IDs.
* Telegram identities resolve into users.
* Existing Telegram history has a migration path.
* Future adapters can reuse the same user model.
