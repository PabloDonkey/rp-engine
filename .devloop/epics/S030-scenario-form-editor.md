# S030 · Scenario form editor — read and edit a scenario without JSON

**Status:** 🟢 In progress — steps 1-5 of 9 done.
**Depends on:** **S010** — admin scenario catalog management. This epic replaces the raw-JSON
editor S010 shipped as its own minimum bar.
**Design source:** [Scenario editing without JSON](https://claude.ai/code/artifact/fda5b259-2e76-4491-8346-79923b0d880d)
— the reviewed proposal, with both page mockups and the field map.
**Effort:** ~3 days
**Risk:** Medium. The work changes a core type, adds a migration, and changes a store port.
The frontend part is low risk. The backend part is not.

## Problem

The admin panel treats a scenario as a text blob.

* [ScenarioDetailPage.vue:67](../../frontend/src/pages/ScenarioDetailPage.vue#L67) prints
  `JSON.stringify(scenario, null, 2)` inside a `<pre>`. There is no reading view.
* [ScenarioEditPage.vue:90](../../frontend/src/pages/ScenarioEditPage.vue#L90) is one
  `<textarea>` of raw JSON, with a hard-coded new-scenario template in the page file.
* [api/index.ts:104](../../frontend/src/api/index.ts#L104) types the payload as
  `z.record(z.string(), z.unknown())`. The client checks nothing.
* [admin_routes.py:244](../../src/rp_engine/adapters/api/admin_routes.py#L244) returns 422 with
  the text "Scenario payload failed validation". No field name.
* `POST /admin/scenarios/import` exists at
  [admin_routes.py:258](../../src/rp_engine/adapters/api/admin_routes.py#L258) and no frontend
  code calls it. Import today means pasting JSON into the edit box.

The cost is real. A missing comma loses the whole save. The `id` field looks editable, but `PUT`
rejects a changed id. Nothing on screen says that `characters` is keyed by role, or what
`UNLISTED` does.

Two more problems came out of the review.

* **The metadata type is wrong.** `ScenarioDefinition`, `World`, `Character` and `StoryBeat` all
  declare `metadata: dict[str, str]`. Real scenarios hold a `tags` array. The list value survives
  because [scenario_serialization.py:152](../../src/rp_engine/infrastructure/scenario_serialization.py#L152)
  passes the value through with no check, and the column is JSONB. Mypy cannot catch it, because
  the payload arrives as `Any`.
* **The panel cannot retire a scenario.** There is no delete route and no lifecycle stamp on the
  definition.

## Goal

Read a scenario as a page. Edit it as a form. Keep JSON for import and export only. Retire a
scenario without erasing it.

## Scope

### 1. Fix the metadata type

No migration. The column is already JSONB.

- [x] `core/metadata.py`: `MetadataValue = str | list[str]`. One home for the alias.
- [x] Apply it to `ScenarioDefinition`, `World`, `Character`, `StoryGraph` and `StoryBeat`.
- [x] Leave `ScenarioSession.metadata`, message metadata and LLM response metadata as
      `dict[str, str]`. The engine writes those and reads them as strings. One such read is
      [builder.py:464](../../src/rp_engine/core/conversation/builder.py#L464).
- [x] Add a metadata normalizer to `scenario_serialization.py`. A string stays a string. A list of
      strings stays a list. A scalar such as `1987` becomes `"1987"`, per item for a list. A nested
      object or a nested list fails the payload.
- [x] Tests for each row of that table.

**Why coerce scalars instead of rejecting them:** the boot import already skips a bad file with a
warning. Losing a whole scenario over one number in a hand-written file is a poor trade.

**Checked before widening:** no production code reads scenario, world or character metadata during
a turn. The type change breaks no reader.

### 2. Soft delete for scenarios

The invariant that makes this safe: **`save()` never writes `deleted_at`.** Only `delete()` and
`restore()` change that column. `import_directory` calls `save()` for every catalog file at every
boot, and an admin edit calls `save()` too. Without the invariant, a retired curated scenario comes
back at the next restart.

- [x] `ScenarioDefinition` gains `deleted_at: datetime | None` and an `is_active` property.
      `ScenarioSession` already carries the same stamp.
- [x] `ScenarioDefinitionStore`: `list_all(include_inactive=False)`, `delete()` becomes the soft
      delete, and a new `restore()`. `get_by_id` keeps resolving. No production code calls the
      current hard `delete`, so nothing breaks.
- [x] Migration `20260811_0013_scenario_soft_delete.py`. One nullable timestamp column. Verify
      `upgrade head` and `downgrade` against a real database.
- [x] `/play <id>` refuses a retired scenario
      ([playthrough_service.py:81](../../src/rp_engine/application/services/playthrough_service.py#L81)),
      with the same reply as an unknown id.
- [x] Running stories keep playing. `chat_service.py:591`, `playthrough_service.py:142` and
      `playthrough_service.py:170` keep resolving by id.
- [x] Export keeps resolving
      ([scenario_transfer_service.py:75](../../src/rp_engine/application/services/scenario_transfer_service.py#L75)).
- [x] The export payload leaves `deleted_at` out. A transfer file describes a scenario, not its
      life inside one database.
- [x] Contract suite: delete hides the scenario from the list, `get_by_id` still resolves, `save`
      does not resurrect, restore works.

### 3. Session count and the two new routes

- [x] `ScenarioSessionStore.count_live_by_definition() -> dict[str, int]`. One grouped query on
      `scenario_sessions` where `deleted_at IS NULL`. One query for the whole list, not one per row.
- [x] `ScenarioSummaryResponse` gains `session_count` and `is_active`.
- [x] `DELETE /admin/scenarios/{id}` retires. `POST /admin/scenarios/{id}/restore` brings it back.
- [x] `GET /admin/scenarios?include_inactive=true`.

### 4. Vitest in browser mode

- [x] Add `vitest`, `@vitest/browser`, `playwright` and `vitest-browser-vue`.
- [x] `vite.config.ts`: the `test.browser` block, Chromium, headless.
- [x] `package.json`: a `test` script.
- [x] One passing test proves the setup before any component depends on it.

Playwright downloads a browser binary once, about 150 MB, through
`npx playwright install chromium`. There is no continuous integration (CI) setup in this
repository, so these tests run on a developer machine only.

**Answered:** the installed version is **Vitest 4.1.10**, one major past what this note
assumed. Vitest 4 uses `browser.instances: [{ browser: "chromium" }]` and moves the
Playwright provider into its own package, `@vitest/browser-playwright`, passed as
`browser.provider: playwright()`. That is a fifth dependency the list above did not name.
`defineConfig` must come from `vitest/config`, not `vite`, or the `test` block type-errors.

### 5. Client schema and typed API

- [x] `frontend/src/api/scenarioSchema.ts`: `ScenarioDefinitionSchema` mirroring
      `scenario_definition_from_payload`, plus the empty-scenario factory that today sits in the
      page file.
- [x] Metadata in the schema: `z.record(z.string(), z.union([z.string(), z.array(z.string())]))`.
- [x] Replace the loose record type in `api/index.ts`. Add `importScenario`, `retireScenario`,
      `restoreScenario`, and the `include_inactive` flag on the list call.
- [x] Store actions for the same.

### 6. Read view

- [ ] `ScenarioDetailPage.vue`: one card per part, in prompt order. Overview, opening scene, world,
      characters, rules, access, metadata, story graph.
- [ ] Metadata renders a list value as chips and a string value as text.
- [ ] Header: the id, the visibility, the live session count, and a retired banner when it applies.
- [ ] Buttons: Retire or Restore, Export JSON, Edit.
- [ ] Keep a collapsed raw-JSON block, read only.

**Section order is not a style choice.** `ConversationBuilder` assembles the prompt as description,
then initial context, then world, then character, then rules. The page follows that order. Access
and metadata sit at the bottom, because they never reach the prompt.

### 7. The form

- [ ] `frontend/src/components/form/`: `TextField`, `TextAreaField`, `StringListField`,
      `MetadataField`, `TagInput`, `OptionCards`, `FormSection`. This creates the first
      `components/` directory in the project.
- [ ] `frontend/src/components/scenario/`: `ScenarioForm`, `WorldFields`, `CharacterCard`,
      `ScenarioReadView`.
- [ ] `id` is locked when editing, and slug-checked when creating.
- [ ] `owner_id` leaves the screen. The form always writes the system owner.
- [ ] `initial_context` gets chips that insert `{{user}}`, `{{char}}` and `{{world}}`.
- [ ] World is a toggle plus a field group. Off writes `null`, not an object of empty strings.
- [ ] Characters are repeating role cards. Role keys must be unique. Zero cards is valid and means
      a freeform scenario.
- [ ] Rules use the list editor, with reorder. Order matters, so the control shows it.
- [ ] Visibility is three option cards, each stating its effect. RESTRICTED reveals the chat id list.
- [ ] Metadata rows carry a text or list switch. List draws tag chips.
- [ ] The story graph stays raw JSON under "Advanced". It is inert data and no scenario uses it. A
      beat editor is not worth building now.
- [ ] A leave guard for unsaved changes.

**The form carries every field, on screen or not.** The form builds the whole payload on save, so
any field without a control is a field the save wipes. That covers `world.metadata`,
`character.greeting` and `character.id`.

### 8. List page

- [ ] Import button. Pick one or more `.json` files, post each to `POST /admin/scenarios/import`,
      then show one result line per file.
- [ ] A "show retired" checkbox, off by default. Retired rows render dimmed, with a Restore button.
- [ ] The live session count on each row.
- [ ] The retire dialog names the live session count before it asks.

### 9. Docs

- [ ] `docs/SCENARIOS.md`: a section on editing in the panel, the retire rules, and the metadata
      value model. Keep the JSON reference as the transfer format.
- [ ] `docs/DATABASE_MODEL.md`: the new column.
- [ ] `docs/DOMAIN_MODEL.md`: the metadata value model and `deleted_at`.

## Order of work

Each step stands on its own.

1. Metadata type and normalizer. No migration, no visible change.
2. Soft delete: column, migration, port, contract cases. Backend only.
3. The two routes and the two response fields. The panel does not use them yet.
4. Vitest in browser mode. One passing test.
5. Client schema and typed API calls. Nothing changes on screen.
6. Read view. Ship it. The edit page still works as raw JSON.
7. Form components and the edit page. Remove the textarea.
8. Import, retire and the checkbox on the list page.
9. Docs and the board.

Steps 1 to 4 ship without touching the panel. Step 6 improves the panel on its own.

## Verification

- [ ] `uv run pytest` green, `uv run mypy .` clean, `uv run ruff check .` clean.
- [ ] `npm run test` and `vue-tsc` green, from step 4 on.
- [ ] `alembic upgrade head` and `alembic downgrade` both verified against a real Postgres.
- [ ] Live check in a browser: create a scenario through the form, play it over Telegram.
- [ ] Live check: retire a scenario with a story running. `/play` refuses it. The running story
      finishes.
- [ ] Live check: restart the app. The retired curated scenario stays retired.
- [ ] Round-trip check: export a scenario with a `tags` array, import the file, compare.

## Tests the epic adds

- `scenarioSchema.ts`: required fields, slug format, duplicate role keys, the empty-scenario factory.
- `MetadataField`: a text row and a list row round-trip, the switch converts both ways, and a
  removed row leaves no empty key.
- `StringListField`: add, remove and reorder produce the right array. Order is load-bearing for
  rules, so this one matters most.
- Visibility: choosing RESTRICTED shows the chat id list, and leaving it clears the list.
- World toggle: off produces `null`.
- The retire dialog names the live session count.
- Backend: the metadata normalizer table, and the four soft-delete contract cases.

## Open questions

- **Deeper metadata.** The value model stops at a string or a list of strings. A nested object has
  no control and fails the payload. If any scenario holds deeper metadata, both the type and the
  control change.
- **Field-level 422.** The server says only "Scenario payload failed validation". Fixing that means
  `scenario_definition_from_payload` returns a reason instead of `None`. That function is shared
  with import, so it belongs in its own change, not this one.
- **Retire and live players.** This epic lets running stories finish. Only `/play` is closed. The
  other reading is that retire should stop them.
