---
id: ADR-015
title: Group Authorization Uses Conversation Identity
status: superseded
created: 2026-07-10
supersedes: []
superseded_by: [ADR-020]
---

# ADR-015 — Group Authorization Uses Conversation Identity

## Context

Milestone 2B introduces Telegram group support with independent authorization behavior.

Private chats and group chats have different trust boundaries:

* private chats are controlled by user-level allowlists
* group chats are controlled by group-level allowlists

If group access is decided per user in group chats, adapter behavior becomes inconsistent and harder to reason about.

## Decision

For Telegram group conversations, authorization is performed at the group identity level.

Rules:

* private chat authorization checks `user_id`
* group chat authorization checks `group_id`
* users in authorized groups inherit access from the group authorization state

Conversation identity resolution remains adapter-owned.

## Rationale

Group chats are shared conversation spaces.

Authorizing by group identity aligns access control with the same identity used for memory isolation and keeps the core layer transport-agnostic.

## Consequences

### Positive

* Consistent policy for all members in an authorized group.
* Cleaner adapter logic for group conversations.
* Clear mapping between authorization boundary and adapter-level group identity.

### Negative

* Group-level authorization grants access to all members, not selected individuals.
