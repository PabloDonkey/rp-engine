# Documentation Drift Audit

You are performing an architecture documentation health check.

Review the repository implementation and compare it against:

- ARCHITECTURE.md
- DOMAIN_MODEL.md
- DECISIONS.md
- ROADMAP.md
- SPEC.md
- VISION.md

The goal is to detect documentation drift.

Do not modify files yet. Produce an audit report only.

## Check for:

### 1. Domain model drift

Compare implemented models/classes/database structures against DOMAIN_MODEL.md.

Look for:

- Implemented entities missing from DOMAIN_MODEL.md
- Documented entities that no longer exist
- Missing relationships
- Incorrect ownership assumptions
- Adapter concepts leaking into domain concepts

Pay special attention to:

- User identity
- External identities (Telegram)
- Character ownership
- Character visibility (private/public)
- Character state vs character definition
- Sessions
- Conversations
- Memory

---

### 2. Architecture drift

Compare actual dependency flow against ARCHITECTURE.md.

Verify:

- adapters -> application -> core -> infrastructure direction
- No Telegram-specific logic inside the RP engine
- LLM provider abstraction is respected
- Persistence concerns are isolated
- Composition root responsibilities are correct

Report any violations.

---

### 3. Decision drift

Review DECISIONS.md.

For every decision:

- Is it implemented?
- Is implementation different from the decision?
- Is the decision obsolete?
- Is a new ADR needed?

Pay attention to:

- LM Studio integration
- provider abstraction
- memory abstraction
- identity separation
- storage decisions

---

### 4. Specification drift

Compare SPEC.md against current behavior.

Find:

- Features implemented but undocumented
- Features specified but missing
- Behavior changes not reflected
- Commands/API behavior differences

---

### 5. Roadmap drift

Review ROADMAP.md.

Identify:

- Completed work not marked complete
- Milestones that no longer match reality
- Missing milestones required by current architecture
- Incorrect ordering/dependencies

---

## Output format

Create:

# Documentation Drift Report

## Summary

Overall health:
(Green / Yellow / Red)

Main issues:

- ...

---

# File-by-file findings

## ARCHITECTURE.md

Status:

Findings:

- ...

Required updates:

- ...

---

## DOMAIN_MODEL.md

...

---

# Missing documentation items

List concepts implemented in code but absent from docs.

---

# Recommended next documentation changes

Prioritize:

P0 - blocks future development
P1 - causes confusion
P2 - cleanup