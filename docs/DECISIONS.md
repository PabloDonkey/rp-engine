# Architecture Decisions — moved

The architecture decision records (ADRs) now live in **[docs/adr/](adr/)**, one decision per file.

* [docs/adr/README.md](adr/README.md) — the index, with status and supersession links.
* [docs/adr/TEMPLATE.md](adr/TEMPLATE.md) — the template for a new ADR.

Nothing was lost in the move. Every ADR body is unchanged; the old `**Status:**` and `**Date:**`
header lines became YAML front matter, which now also records both directions of every
supersession link.

This file stays behind because older links point at it — commit messages, archived epics in
`.devloop/archive/`, and the prompt files in `ai/prompts/`. Do not add new ADRs here.

| Looking for | Now at |
|---|---|
| ADR-013 — Separate Conversation Storage and Memory Strategy | [0013](adr/0013-separate-conversation-storage-and-memory-strategy.md) |
| ADR-023 — Scenario-Centric Architecture | [0023](adr/0023-scenario-centric-architecture.md) |
| ADR-024 — Postgres as Sole Persistence Backend | [0024](adr/0024-postgres-as-sole-persistence-backend.md) |
| ADR-025 — Session Reset Tiers | [0025](adr/0025-session-reset-tiers.md) |
| ADR-026 — Layered Memory | [0026](adr/0026-layered-memory.md) |
| anything else | [the index](adr/README.md) |
