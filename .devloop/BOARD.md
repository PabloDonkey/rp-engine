# RP Engine — Dev Board

<!--
  Rendered as a kanban by the VSCode extension "Markdown Kanban"
  (id: lowrank.vscode-markdown-kanban). Columns = `##` headers, cards = top-level
  list items. Drag cards between columns in the board view; the file rewrites itself.
  It is also just plain markdown, so it reads fine without the extension.
  Workflow rules: see README.md in this folder.
-->

## 🔵 Backlog

- Activate StoryGraph / scenario branching — `StoryGraph`+`StoryBeat` exist as inert data; nothing drives beats yet. _(bare card — gets an S### when promoted to an epic)_ → see `../docs/DOMAIN_MODEL.md`

## 🟡 Up Next

<!-- Finishing the PG integration — audit 2026-07-23. Ordered: S004 first (unblocks parity),
     then S005/S006 (test coverage), S007/S008 (hardening + docs). -->

- **S004** · PG parity for identity + trace stores — GenerationTrace/UserIdentity/GroupIdentity still hard-wired to JSON even in `postgres` mode; add models + migration 0007 + PG stores + contracts. _(core gap)_ → [epic](epics/S004-pg-identity-trace-stores.md)
- **S005** · Conversation store contract (both backends) — `PostgresConversationStore` has zero test coverage; extract shared contract, run JSON + PG. → [epic](epics/S005-conversation-store-contract.md)
- **S006** · Migration-vs-model integrity tests — PG contracts use `create_all`, never Alembic; migrations are untested. Add upgrade/downgrade round-trip + migrate-then-contract. → [epic](epics/S006-migration-integrity-tests.md)
- **S007** · DB startup health probe + `/health` — no boot-time connectivity check; failures surface lazily. Add `SELECT 1` probe + `db` in `/health`. → [epic](epics/S007-db-startup-health-probe.md)
- **S008** · Remove legacy WorldStore + DB docs refresh — delete the unwired character-era `WorldStore` port/impl/test + orphaned `default_world_id`; rewrite character-centric `DATABASE_MODEL.md`. → [epic](epics/S008-remove-worldstore-docs.md)

## 🟢 In Progress

_(nothing active)_

## ✅ Done (recent)

<!-- Newest first. Trim this column when it gets long — full record lives in archive/. -->

- **S003 · 2026-07-23 · Multiple scenario catalog paths + fix `.env.example`** — `scenario_catalog_dirs: list[str]` (comma-delimited), `ScenarioCatalog.from_directories(...)` merges dirs (later wins on id collision), `.env.example`/README/SCENARIOS.md updated. Verified: 214 passed / 2 skipped, mypy clean on `src/`, ruff clean. → [archive](archive/S003-2026-07-23-multi-catalog-paths.md)
- **S002 · 2026-07-23 · Fix LM Studio `result.content` crash** — fix already landed with the scenario migration (`_extract_content` normalizes str/dict/object; log uses normalized content). Verified: 6/6 provider tests, 208 passed / 2 skipped, mypy + ruff clean. → [archive](archive/S002-2026-07-23-lmstudio-content-fix.md)
- **2026-07-22 · Scenario access control + drop RoleProfile** — `ScenarioVisibility` (PUBLIC / UNLISTED / RESTRICTED) + `allowed_group_chat_ids` allow-list; migrations 0005/0006; RoleProfile removed. Commit `59dc049`.
- **S001 · 2026-07-22 · Scenario-centric migration (Phase 0–7)** — character-centric → scenario-native engine, JSON + Postgres at parity. → [archive](archive/S001-2026-07-22-scenario-migration.md) · ADR-023
