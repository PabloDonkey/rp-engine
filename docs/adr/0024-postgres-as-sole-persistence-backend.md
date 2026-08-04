---
id: ADR-024
title: Postgres as Sole Persistence Backend
status: accepted
created: 2026-07-24
supersedes: [ADR-023]
superseded_by: []
---

# ADR-024 — Postgres as Sole Persistence Backend

## Context

ADR-023 established dual persistence — JSON and PostgreSQL kept at parity behind a shared
serializer and one contract-test suite run against both backends — as a deliberate
transitional strategy while the scenario-centric model and the Postgres store
implementations were being built out. That build-out is now done (S001–S008): every store
port has a `Postgres*Store` implementation, migrations are integrity-tested against a real
DB (S006), a startup health probe exists (S007), and a one-time JSON→Postgres migration
script has shipped for existing deployments. `RP_ENGINE_PERSISTENCE_BACKEND` still defaults
to `"json"`, so the transitional dual-backend state has outlived its purpose.

This came to a head planning S010 (admin panel scenario-catalog editing), whose open
question was "does an edited scenario live in Postgres or get written back to JSON?" —
which turned out to be deeper than a config default. Today `PlaythroughService` lists and
starts scenarios from an in-memory `ScenarioCatalog` loaded once at boot from a curated JSON
directory (`app/main.py` → `ScenarioCatalog.from_directories(settings.scenario_catalog_dirs)`);
`ScenarioDefinitionStore` (JSON or Postgres, whichever backend is active) is only ever
written to as a derived cache once a playthrough begins
(`playthrough_service.py::_begin` → `self._scenario_definition_store.save(scenario)`), and
read back only as a fallback in `restart`. So a hypothetical admin panel that wrote scenario
edits into `ScenarioDefinitionStore` would not actually make them playable — `/play` would
keep serving the stale catalog copy. Two parallel scenario sources, not one, is the actual
problem dual persistence left unresolved.

## Decision

**Postgres becomes the only runtime persistence backend.** Concretely:

* All six JSON store implementations (`storage/json_scenario_definition_store.py`,
  `json_scenario_session_store.py`, `json_conversation_store.py`, `json_user_identity_store.py`,
  `json_group_identity_store.py`, `json_generation_trace_store.py`) are **deleted**, not
  deprecated. `Settings.persistence_backend` and the branch in `build_container` are removed;
  the composition root wires the Postgres stores unconditionally. This follows the same
  no-back-compat precedent ADR-023 set for the character→scenario cutover: the project is
  pre-release, and carrying a second live backend costs more (surface area, the contract-test
  matrix, the "which one is source of truth" ambiguity above) than it returns.
* **`ScenarioDefinitionStore` becomes the live source for scenario listing/starting/resuming.**
  `PlaythroughService` is rewired to query the store directly (`find_by_owner` /
  `get_by_id`) instead of `ScenarioCatalog`; the `catalog` constructor parameter and the
  catalog wiring in `build_container` are removed. This closes the two-sources-of-truth gap
  above and is the change that actually resolves S010: the admin panel writes scenarios into
  `ScenarioDefinitionStore`, and `/play` sees them immediately because it reads from the same
  place.
* **`ScenarioCatalog`'s JSON-loading code is repurposed, not deleted.** Its directory-walking
  and validation logic becomes the basis of a scenario **import/export utility** exposed as an
  admin panel feature: import pushes JSON scenario payloads into `ScenarioDefinitionStore`
  (used once to seed a fresh DB with the existing curated set, and afterward for
  bringing in new hand-authored scenarios); export serializes a stored scenario back to the
  same JSON shape for backup/portability. The same import/export treatment extends to
  `ScenarioSession` (+ its conversation transcript), for backing up or restoring a
  playthrough. Once a scenario has been imported, Postgres is authoritative — the admin panel
  is the only place scenarios and sessions are *authored/edited* going forward; JSON is a
  transfer format, not a live source.
* **The test suite gains an auto-managed Postgres fixture** (e.g. testcontainers) so
  `uv run pytest` keeps working with no manual `docker compose up` step. The JSON leg of the
  shared contract-test suite (`tests/.../contracts/`) is deleted; the Postgres contract run
  becomes the only one and stops being gated behind `RP_ENGINE_RUN_POSTGRES_TESTS` for the
  default `pytest` invocation (a separate live-DB-only suite may still exist for anything the
  managed fixture can't cover, e.g. real-migration integrity tests per S006).
* The detailed cutover (deleting the JSON stores, rewiring `PlaythroughService`, building the
  import/export utility, wiring the test fixture) is tracked as its own epic,
  `.devloop/epics/S013-retire-json-persistence.md`, since it spans more than S010's
  admin-panel slice. S010 depends on it.

## Alternatives

* **Keep JSON as a supported offline/local-dev mode** (Postgres default, JSON opt-in) —
  rejected: it preserves exactly the "two sources of truth" ambiguity this ADR exists to
  remove, for a use case (zero-dependency local trial) the new testcontainers-backed test
  fixture and `scripts/db_services.sh` already cover with one `docker compose up`.
* **Deprecate now, delete later** (flip the default, leave JSON code in place, remove it in a
  follow-up story) — rejected: for a pre-release codebase, a half-removed backend is worse
  than either fully-present or fully-gone — it still has to be reasoned about but no longer
  gets test coverage. Matches the one-shot removal precedent from ADR-023's own follow-up
  cleanup.

## Rationale

* Removes the actual ambiguity blocking S010: one scenario source, not two.
* Matches the project's stated no-v1-back-compat stance (ADR-023) rather than introducing a
  new instance of exactly the parallel-path problem that ADR rejected.
* Recycles rather than discards the JSON catalog code — it becomes the import/export path
  instead of dead weight.
* Simplifies the composition root and shrinks the contract-test matrix from "two backends,
  kept at parity" to "one backend, tested directly."

## Consequences

### Positive

* Single, unambiguous source of truth for scenarios and sessions — unblocks S010.
* `build_container`, `Settings`, and the contract-test suite all get simpler.
* The recycled catalog code gives the admin panel a real import/export feature instead of
  being retired outright.

### Negative

* Postgres becomes a hard dependency to run the app or the test suite at all — there is no
  more zero-setup JSON fallback. Mitigated by the testcontainers-backed pytest fixture and
  `scripts/db_services.sh`, but it's a real loss of the "just clone and run" simplicity ADR-001
  (Local-First Architecture) valued; Postgres itself stays local (docker compose), so the
  local-first *principle* holds, but the on-ramp gets heavier.
* A fresh/empty Postgres database has no curated scenarios until the import step runs once —
  unlike today, where the JSON catalog directory ships them for free at every boot. The
  import/export utility (S013) must exist before or alongside the JSON-store deletion, not
  after, or `/play` regresses to empty on a fresh deploy.
* `PlaythroughService`, `build_container`, and every JSON store's call sites need updating in
  the same change — this is not a config-only flip.

## Supersedes

* Supersedes the dual-persistence-backend decision in ADR-023 ("Both persistence backends...
  kept at parity via a shared serializer and one contract-test suite run against both
  backends"). ADR-023's scenario-centric domain model itself is unaffected.
