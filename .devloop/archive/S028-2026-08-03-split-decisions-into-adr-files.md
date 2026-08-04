> 🗄️ **ARCHIVED — COMPLETED 2026-08-03.** Frozen; do not edit. Kept as evolution history.
> **Result:** `docs/DECISIONS.md` (26 ADRs, 1926 lines) became `docs/adr/`, one ADR per file,
> each with YAML front matter carrying `status`, `created`, `supersedes`, and `superseded_by`.
> ADR bodies were moved **unchanged** — a verification script proved all 26 byte-identical
> apart from the `**Status:**`/`**Date:**` header lines that became front matter. The back
> link (`superseded_by`) did not exist anywhere before; it does now, in both directions, and a
> test enforces the mirror. That test immediately paid for itself: it caught that ADR-015 was
> superseded by **ADR-020**, not ADR-021 as first recorded here.

# S028 · Split `DECISIONS.md` into `docs/adr/` — one ADR per file

**Status:** ✅ COMPLETE (2026-08-03)
**Depended on:** nothing. Documentation move; the only source change was two comment lines.
**Actual effort:** one session.

## Problem

`docs/DECISIONS.md` was one file with **26 ADRs and 1926 lines**. Three costs:

1. **Reading.** Finding one decision meant scrolling or grepping a 1900-line file.
2. **Relations were prose, not data.** "Supersedes" appeared as a `## Supersedes` section in
   ADR-020, ADR-023, ADR-024 and ADR-026, and nowhere else. **No ADR said which ADR replaced
   it** — the back link was missing across the whole document.
3. **Status was unreliable.** ADR-015 was marked `Superseded` with no pointer to its
   replacement. ADR-025 carried an inline *Amendment* section, a fourth way of saying "this
   changed".

## What shipped

```
docs/adr/
  README.md              ← index table (id, title, status, created, replaced-by) + the rules
  TEMPLATE.md            ← the old "Future Decisions" template, now with front matter
  0001-local-first-architecture.md
  …
  0026-layered-memory.md
docs/DECISIONS.md        ← stub pointing at docs/adr/, kept for old links
tests/unit/docs/test_adr_files.py   ← the checker
```

File name is `NNNN-kebab-title.md`, zero-padded to four digits so plain sorting stays correct
past ADR-99.

## Front matter contract

```yaml
---
id: ADR-024
title: Postgres as Sole Persistence Backend
status: accepted            # proposed | accepted | superseded | rejected
created: 2026-07-26
supersedes: [ADR-023]
superseded_by: []
---
```

## The four open questions, and what was decided

- [x] **Partial supersession.** Kept `supersedes`/`superseded_by` as plain id lists, and made a
      `## Supersedes` prose section **required** whenever `supersedes` is non-empty — the prose
      states the scope, the list stays simple. Structured `{adr, scope}` entries were rejected as
      YAGNI. Rule: `status: superseded` means the *whole* ADR is dead; an ADR that lost only some
      rules keeps `status: accepted` and records the replacement in `superseded_by`. Only ADR-015
      is fully superseded. ADR-013, ADR-020, ADR-022 and ADR-023 are partial.
- [x] **Amendments.** Kept as dated `## Amendment` body sections. Requiring a new ADR for a small
      additive clarification would inflate the numbering for no gain. Documented in `TEMPLATE.md`:
      the only edits an existing ADR may receive are its `superseded_by` line and an amendment.
- [x] **`created` dates.** ADR-010 onward already carried a `**Date:**` line — those were used as
      written, since they are the author's own record. ADR-001 to ADR-009 had none and were dated
      from git (`git log -S "<title>" -- docs/DECISIONS.md`, first commit), which put all nine on
      2026-07-10, the date of the first commit. Note the file was renumbered at some point:
      searching by ADR *number* gives dates shifted by one, so the title search is the correct one.
- [x] **Status vocabulary.** Lowercase in front matter, and the body `**Status:**`/`**Date:**`
      lines dropped — one fact in one place. A test enforces that they do not come back.

Two facts that lived inside a `**Status:**` line were not status and were kept as their own body
lines: ADR-025's `**Implemented:** 2026-07-27 (S015; …)` and ADR-026's `**Scope:** design only…`.

## Work done

### Phase 1 — decide and prepare
- [x] Settled the four questions above.
- [x] Wrote `docs/adr/README.md`: index table, file naming, the front matter contract, how to add
      an ADR, how to change one.
- [x] Extracted the "Future Decisions" template into `docs/adr/TEMPLATE.md`, rewritten around the
      front matter (its old `**Status:**` line was obsolete) and given a `## Supersedes` section.

### Phase 2 — the move
- [x] Split all 26 ADRs mechanically with a script, bodies **unchanged**. No rewording.
- [x] Filled `created` for every ADR.
- [x] Filled both directions of every supersession link:
      - **ADR-020** supersedes ADR-015 (where it tied storage identity to transport identity)
      - ADR-023 supersedes ADR-020 (`Session` ownership) and narrows ADR-022 (character cards)
      - ADR-024 supersedes the dual-backend part of ADR-023
      - ADR-026 supersedes three milestone-scoped rules of ADR-013
- [x] `docs/DECISIONS.md` reduced to a stub with a small "looking for / now at" table. Not
      deleted: 40 references pointed at it.

### Phase 3 — fix the references
- [x] Repointed the live docs: `CLAUDE.md` (both the ADR-023 note and the documentation map),
      `README.md` (3), `docs/ARCHITECTURE.md` (2), `docs/DATABASE_MODEL.md`, `docs/SCENARIOS.md`,
      `.devloop/README.md`, `.devloop/BOARD.md` (the S021 card's ADR-026 link, now deep),
      and the S021 epic.
- [x] Repointed the two source comments:
      [scenario_transfer.py](../../src/rp_engine/infrastructure/scenario_transfer.py) and
      [main.py](../../src/rp_engine/app/main.py).
- [x] Left `ai/prompts/*` and `.devloop/archive/*` untouched — archived epics are frozen by the
      `.devloop` rules and the prompt files are a historical record. The stub keeps those links alive.

### Phase 4 — the checker (kept, not cut)
- [x] `tests/unit/docs/test_adr_files.py`, 158 cases. Per file: the name matches the convention
      and the `id`; the status is in the vocabulary; `created` is `YYYY-MM-DD`; the H1 matches the
      front matter; no `**Status:**`/`**Date:**` line came back into the body; every
      `supersedes`/`superseded_by` id resolves **and is mirrored on the other side**; a non-empty
      `supersedes` has its `## Supersedes` prose. Plus: the index lists every file.
- [x] Front matter is parsed by hand, **not** with PyYAML. PyYAML is present in the venv only as
      a transitive dependency; a test that imported it would depend on something this project does
      not declare. The contract is six scalar-or-flat-list lines, so a real parser buys nothing.

## Verification

- [x] **Nothing lost.** A verification script rebuilt each ADR from the new files and diffed it
      against the original block: **26 checked, 0 differ**. The only lines in the old file not
      carried into a new one are its 4-line preamble and the separators — the preamble is now the
      opening of `docs/adr/README.md`.
- [x] Every markdown link inside the new files resolves. The ADR bodies contained no relative
      links of their own, so the move broke none.
- [x] `uv run pytest` green, `uv run ruff check .` clean, `uv run mypy .` — `src/` clean (0
      errors; the 148 test-file errors are pre-existing and none are in `tests/unit/docs/`).

## What the checker caught

The first mapping recorded **ADR-021** as superseding ADR-015, read from a `## Supersedes` section
near the ADR-020/ADR-021 boundary. The section belongs to **ADR-020**. The mirror test failed on
`0021-remove-character-state.md` — it had `supersedes: [ADR-015]` and no `## Supersedes` section to
justify it — and the three files were corrected.

That is the argument for the checker existing. Machine-readable front matter that nothing reads
back is just a prettier header, and this repo already learned in S016 that fixing the code while
leaving the data wrong does not count as fixed.

## Notes

- No ADR was written for this change. It is a documentation layout change, not an architecture
  decision.
- The "do this after S021" warning on the original card was moot: ADR-026 was already written into
  `DECISIONS.md`, and S021's remaining work is in `ARCHITECTURE.md`, `DOMAIN_MODEL.md`,
  `DATABASE_MODEL.md` and `ROADMAP.md`. Nothing else was pending in the file.
