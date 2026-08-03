# S021 · Memory architecture — ADR-026 and the design docs

**Status:** 🟢 In Progress (started 2026-08-02)
**Effort:** ~1 day. Design only, no code.
**Risk:** Low to build, high to get wrong. Five sources will depend on the contracts written here.
**Design source:** [Five ways to remember a story](https://claude.ai/code/artifact/c77560f4-99c2-4566-8b1c-9687d3893ac5)
— Pablo's chosen architecture. ADR-026 cites it.

## Goal

Write the memory architecture down before any of it is built. The toggle architecture, the
fragment contract and the budget rules are expensive to change once five sources depend on them,
and cheap to get right on paper.

## Tasks

- [x] **ADR-026** in `docs/DECISIONS.md` — the `MemorySource` port, `MemoryFragment`,
      `MemoryPipeline`, per-session `MemorySettings`, the five layers, the build order
      S022→S026, the deferred embedding decision, and the partial supersession of ADR-013.
- [ ] **`ARCHITECTURE.md`** — it already describes a "Memory Manager" that ADR-013 forbade.
      Rename it to `MemoryPipeline` and make the description match ADR-026.
- [ ] **`DOMAIN_MODEL.md`** — `MemorySettings` on `ScenarioSession`, next to `SessionDirectives`.
- [ ] **`DATABASE_MODEL.md`** — the tables layers 01 to 03 will add, and the note that
      `MemorySettings` rides the existing session JSONB with no new column.
- [ ] **Per-source specs** — one short section per layer: what it stores, what it returns, what
      its `observe` half does, and what it costs per turn.
- [ ] **`ROADMAP.md`** — add the memory milestone.

## Decisions ADR-026 leaves to this epic

- [ ] **Background worker mechanism.** ADR-026 states the shape is decided once, here, and not
      per epic. Pick one: an `asyncio.create_task` started by the calling service, or a runtime
      component owned by `app/lifespan.py`. S023 may skip it and summarize inline. S025 cannot.
- [ ] **Token counter.** Real tokenizer dependency, or a calibrated heuristic. This blocks S022.
- [ ] **Where the window's overflow goes when layer 01 is off** — dropped in silence, or logged.
- [ ] **What `recall` receives** — the whole `ScenarioSession`, or a narrow read model.

## Verification

Design epic, so the bar is review, not tests.

- [ ] The ADR and the four docs agree with each other. One name per thing: `MemoryPipeline`, not
      "memory manager" in one file and "pipeline" in another.
- [ ] Every claim about current code still holds when S022 starts.
- [ ] `python3 ~/.claude/skills/ste-writing/scripts/ste-lint.py docs/*.md` stays under 2.0 per
      100 words for the files this epic touches.
