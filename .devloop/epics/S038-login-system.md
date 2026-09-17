# S038 · Login system

**Status:** 🔵 Backlog — design not started
**Effort:** TBD, pending design
**Risk:** TBD, pending design

## Context

The admin panel has had no authentication since S009 — it relies on Tailscale network
trust instead (see `docs/ARCHITECTURE.md`, `docs/adr/`). This epic reserves the story id
for a login system; the design itself is the first piece of work, not yet started.

## Scope

Not yet defined. Design first, then fill in this section.

## Open questions for the design pass

- Who logs in: the single operator only, or multiple named accounts?
- Session mechanism (cookie, token) and where it fits the hexagonal layering — `core/`
  cannot depend on a framework, so session verification is an `adapters/api/` concern,
  same as `TelegramAuthorization` is transport-owned today.
- Whether this replaces the Tailscale-trust model or adds a second layer on top of it.
- Interaction with the existing `telegram_admin_user_id` / `TelegramAuthorization`
  authorization policy — one identity system, or two coexisting ones?
