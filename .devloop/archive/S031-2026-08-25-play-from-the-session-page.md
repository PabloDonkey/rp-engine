> 🗄️ **ARCHIVED — COMPLETED 2026-08-25.** Frozen; do not edit. Kept as evolution history.
> **Result:** the panel can advance a story. Three routes on the admin router wrap the same
> `ChatService` methods Telegram has driven since S014, and they answer with the *stored*
> narrator message so the turn number and the finish reason arrive with the text.
> **One generation per session, and it refuses rather than queues.** Nothing previously
> stopped a turn arriving from Telegram and the browser at once, and both would have built a
> prompt from a history about to change underneath. The guard is an in-process set, which
> holds only while the two surfaces share a process — the docstring says so, because that is
> the assumption that goes quiet if they are ever split.
> **The page was reordered around the story.** It was the *last* block on a 697-line column,
> below a memory section larger than the transcript itself. Persona, Memory and Directives
> are now closed panels that still name their own value, the transcript owns a scroll region,
> and S012's four per-message checkboxes moved behind a `···` — which matters more than it
> looks, because Retry *replaces* a reply and those traces are the only place the discarded
> one survives.
> **The composer is a `[ Send ▾ ]` split button.** Three rules hold it: the draft survives the
> menu, a blocked item is greyed with its reason rather than hidden, and Send never becomes
> another action. Continue reads **Finish reply** when the last turn stopped at the token cap,
> which costs nothing — the finish reason was already on the message.
> **No login, no new dependency, no migration, no core port change.** Reka UI was considered
> twice and declined twice.
> **⚠️ Five live checks are open** — a real browser, a real model, a real phone. Nothing below
> was run against any of them.

# S031 · Play a turn from the session page

**Status:** ✅ COMPLETE — all 9 steps done on `feat/S031-play-from-session-page`.
821 backend tests and 79 frontend tests pass; `mypy src`, `ruff check` and `vue-tsc` clean.
**Five live checks are open** and are listed under Verification — nothing below has been run
against a real browser, a real model, or a real Telegram client.
**Depends on:** **S009** (the admin panel and its session page), **S012** (the per-message debug
filters this epic moves), **S029** (the memory block this epic collapses).
**Design source:** [The Play View](https://claude.ai/code/artifact/bed99962-de97-4c5b-88d9-302fd4c2a65e)
— the reviewed layout proposal, with the page mockup, the three scroll states, and the split
button.
**Effort:** ~2 days. Most of it is frontend.
**Risk:** Low. No migration, no core port change, no new dependency, no change to how a turn is
generated. The backend part is thin wrappers over services that already exist.

## Problem

Telegram is the only place a story can be played. The panel can read a story in full and operate
on it, but it cannot advance it.

The engine is not the obstacle. The application layer already exposes everything a play surface
needs, and the Telegram adapter proves it. The adapter declares a Protocol for exactly that set
at [adapter.py:185](../../src/rp_engine/adapters/telegram/adapter.py#L185): `list_scenarios`,
`get_active`, `start`, `restart`, `clear`, `set_persona`, `resume_text`, `set_language`,
`add_rule`, `remove_rule`, `add_director_instruction`, `set_memory_source`. Every one of those is
a real method today.

What is missing is the surface.

* The player HTTP API is three routes — [routes.py:10](../../src/rp_engine/adapters/api/routes.py#L10)
  `/chat`, [:22](../../src/rp_engine/adapters/api/routes.py#L22) `/continue`,
  [:29](../../src/rp_engine/adapters/api/routes.py#L29) `/memory/clear`. There is no retry route
  and no way to start a story.
* Those three take an `owner_id` string and trust it
  ([models.py:8](../../src/rp_engine/adapters/api/models.py#L8)). Anyone who knows a session id
  can post a turn into it. The panel is unauthenticated too (S009, Tailscale trust), so this epic
  changes no security posture. But the new routes must not make the hole wider, which is why
  they hang off the admin router rather than adding a second unauthenticated entry point.
* The panel's session page has no composer.

There is a second problem the layout work exposed, and it is the reason this is not simply
"add a text box".

**The story is the last thing on the page.** [SessionDetailPage.vue](../../frontend/src/pages/SessionDetailPage.vue)
is 697 lines and one long column. Measured in template lines:

| Block | Lines | Where |
|---|---:|---|
| Title, actions, status chips | ~30 | [:267](../../frontend/src/pages/SessionDetailPage.vue#L267) |
| Player persona | ~74 | [:298](../../frontend/src/pages/SessionDetailPage.vue#L298) |
| Memory — bars, layer switches, recap | ~171 | [:372](../../frontend/src/pages/SessionDetailPage.vue#L372) |
| Directives — language, rules, director | ~52 | [:544](../../frontend/src/pages/SessionDetailPage.vue#L544) |
| **Transcript** | ~102 | [:597](../../frontend/src/pages/SessionDetailPage.vue#L597) |

To reach the first line of story you scroll past the memory block, which alone is larger than the
transcript. Inside the transcript, every narrator message carries a permanent row of four
checkboxes — Thinking, Raw trace, System prompt, Turn metadata, added in S012 at
[:629](../../frontend/src/pages/SessionDetailPage.vue#L629). Correct when debugging one reply.
Noise under every paragraph when reading a story.

And the window scrolls the whole page. There is no scroll container to pin a composer under or to
scroll to the newest turn.

## Goal

Send a turn, continue, and retry from the session page. Story first, debug machinery one click
away. No login, no second route, no mode switch.

## Scope

### 1. Turn routes on the admin router

New file `adapters/api/play_routes.py`, mounted on the existing `/admin` prefix from
[admin_routes.py:37](../../src/rp_engine/adapters/api/admin_routes.py#L37). Identity comes from
the session id in the path. The panel already knows whose story it is, because you walked
user → sessions → this one.

- [x] `POST /admin/sessions/{session_id}/turn` — body `{"message": "..."}` →
      `ChatService.send_message` ([chat_service.py:118](../../src/rp_engine/application/services/chat_service.py#L118)).
- [x] `POST /admin/sessions/{session_id}/continue` →
      `ChatService.continue_story` ([:201](../../src/rp_engine/application/services/chat_service.py#L201)).
- [x] `POST /admin/sessions/{session_id}/retry` →
      `ChatService.regenerate_last_response` ([:266](../../src/rp_engine/application/services/chat_service.py#L266)).
- [x] All three return the stored narrator message, not a bare string. The client needs the turn
      number and the finish reason, and it should not have to refetch the transcript to get them.
- [x] `ValueError` from the service becomes a 409 with the service's own text. Retry raises it for
      "last message is not a character reply", and that sentence is the right thing to show.
- [x] A retired session (`deleted_at` set, S016) refuses all three with a 409.

**Why on the admin router and not a new `/play` one.** These are operator actions on a chosen
session, which is what the panel does everywhere else. S015 already set that precedent with
`override_persona` — "an operator exception the player-facing guard never sees". A separate
player router would imply a player identity that does not exist here.

**Added beyond the written scope:** `LLMError` becomes a **502**. The epic only named the
409 cases. Without this arm a model that is down returns a bare 500 with no body, and the
pending row in the panel has nothing to show the player. Two lines, and it keeps "the model
failed" separate from "your request was wrong".

**Left alone:** the three existing routes in `routes.py`. They are wired into the composition root
at [main.py:312](../../src/rp_engine/app/main.py#L312) and nothing in this epic needs them.
Removing them is its own decision.

### 2. One generation per session at a time

There is no guard today. Nothing stops a turn being sent from Telegram and from the browser at
the same time, and both would generate against the same session. With a Send button in front of
you this stops being theoretical.

- [x] An in-process lock keyed by session id, in `ChatService`. Try to acquire; if it is held,
      raise a "this story is already generating" error rather than waiting.
- [x] The three entry points that generate — `send_message`, `continue_story`,
      `regenerate_last_response` — take it. `clear_conversation` does not generate and does not
      need it.
- [x] The adapter turns the busy error into a 409. Telegram shows it as a normal reply.

**The assumption this rests on:** Telegram and FastAPI run in one process, wired together in
[main.py](../../src/rp_engine/app/main.py). An in-process lock is therefore enough. Write that
down in the docstring, because it is the thing that silently stops being true if the two surfaces
are ever split.

### 3. Client API and store

- [x] Three functions in [api/index.ts](../../frontend/src/api/index.ts), beside the existing
      session calls, with a zod schema for the returned message.
- [x] Three actions in [stores/admin.ts](../../frontend/src/stores/admin.ts).
- [x] The optimistic path, which is the part that matters: push the player's message into
      `transcript` **before** the request goes out, push a pending narrator row after it, then
      replace that row with the reply. On failure the pending row becomes an error row and the
      player's text stays on screen.

**No polling.** Vue reactivity follows the store, not the server; nothing in Vue reports a change
in Postgres. The only case a poll would catch is a turn arriving from Telegram while the page is
open, and step 2 exists to prevent exactly that. Fetch on load, reload after a Telegram session.

### 4. The transcript becomes a scroll region

- [x] The transcript gets its own height and `overflow-y: auto`. Today the window scrolls the
      whole page, so there is nothing to scroll to the bottom of and nothing to pin under.
- [x] The composer sits below it and does not move.

### 5. Stick to the bottom, unless I am reading

- [x] A composable holding one piece of state: is the container within ~96px of the bottom.
- [x] Measure **before** appending, act after. Measured afterwards the answer is always "no",
      because the content just added is what pushed the view away from the bottom.
- [x] Following → new content scrolls in. Reading → nothing moves, and a "jump to latest" pill
      appears with a count of unseen turns. The pill does not exist while following.
- [x] Tapping the pill scrolls to the newest turn and clears the count.

**No Reka UI.** Its `ScrollArea` restyles the scrollbar and exposes the viewport element; the
"am I at the bottom" test is still ours to write. Not worth a dependency.

### 6. The composer, as a split button

`[ Send ▾ ]`. Continue and Retry live in the menu, which is where later commands go without the
composer growing each time.

- [x] Send is primary, disabled while the box is empty, and never changes into another action.
- [x] **The draft survives the menu.** Continue and Retry ignore the text box, so they must leave
      it untouched. The draft is still there to Send afterwards. A menu item that silently eats
      your typing is the worst bug this pattern invites.
- [x] **A blocked item is greyed with its reason beside it, not hidden.** Retry needs the last
      message to be a narrator reply. Hiding it instead makes the menu change height between
      openings, so the item you were reaching for moves under your finger.
- [x] The Continue item reads **Finish reply** when the last narrator turn was cut off at the token
      limit, and **Continue** otherwise. This costs nothing: `_should_resume`
      ([chat_service.py:705](../../src/rp_engine/application/services/chat_service.py#L705)) reads
      `was_truncated`, which comes from the finish reason already stored in the message metadata
      ([:712](../../src/rp_engine/application/services/chat_service.py#L712)) and already returned
      by `GET /admin/sessions/{id}/transcript`.
- [x] Keyboard: arrow keys, Enter, Escape, click outside, focus back to the trigger.
      `aria-haspopup` and `aria-expanded` on the trigger. The menu opens upward. It sits at the
      bottom of the screen, and on a phone the keyboard is under it.
- [x] While a turn is generating: composer disabled, and the pending row from step 3 is what tells
      you the app is working. A reply takes tens of seconds with no streaming, and without a
      visible pending state the page reads as broken.

**Hand-rolled, not Reka.** Reka's `DropdownMenu` does handle the keyboard properly. Two items do
not justify pulling a primitive set in. Revisit when the menu is full.

### 7. Persona, Memory and Directives start closed

- [x] The three blocks become closed disclosures in a strip under the title. Contents unchanged. Only the wrapper
      changes.
- [x] Each closed row shows its current value, so state is readable without opening anything:
      the persona name, the memory percentage, the language and rule count.
- [x] They open in place and push the transcript down.

**This is not a mode.** No switch, nothing to remember, no second code path. Three panels whose
default is closed.

### 8. Per-message debug behind a `···`

- [x] The four S012 checkboxes move behind a `···` control on the narrator message. Same four
      filters, same behaviour, one click away.
- [x] It has to stay reachable, and this is why: **Retry replaces the reply it regenerates.** The
      discarded text leaves the transcript. Both attempts are recorded as generation traces under
      the same turn number, so the traces panel behind this control is the only route back to what
      was thrown away.

### 9. Docs

- [x] `docs/ARCHITECTURE.md` — the panel is now a play surface as well as a read surface, and the
      command flow for a turn sent from the API.
- [x] `CLAUDE.md` — the line "Telegram is the primary, fully-featured surface" needs qualifying.
- [x] `.devloop/BOARD.md` — card moved to Done, and the streaming/cancel card added to Backlog
      (see Out of scope).

## Order of work

1. Steps 1 and 2 together. The guard is easier to write while the routes are being written than
   bolted on after, and both are backend with real tests.
2. Step 3. Prove the round trip with the existing page before changing any layout.
3. Steps 4 and 5. Scrolling is the part most likely to need fiddling in a real browser.
4. Step 6.
5. Steps 7 and 8. Pure presentation, safe to do last, easy to cut if the epic runs long.
6. Step 9.

## Verification

- [x] `uv run pytest` green — 821 passed.
- [x] `uv run ruff check .` clean.
- [x] `uv run mypy src` clean, 124 files.
- [x] `npm run test` green — 79 passed, from a cold dependency cache. `npm run build`
      (`vue-tsc -b && vite build`) clean.

**`uv run mypy .` is not clean, and was not made clean.** It reports 152 errors across 18
test files, and the count is identical with this branch stashed — every one of them predates
S031. The bar this epic held itself to is the one the repository actually meets: `src/` is
mypy-clean. Closing the gap in `tests/` is its own change.

**⚠️ The five live checks below are open.** Everything above ran and passed. Nothing below
has been run against a real browser, a real model, or a real Telegram client.

- [ ] Play five turns in a browser against a real model. Read one back mid-generation and
      confirm the view does not jump when the reply lands.
- [ ] Retry from the menu. The old reply leaves the transcript, and both attempts are in the
      traces behind the `···`.
- [ ] Continue on a reply that stopped at the token cap. The item reads **Finish reply** and
      the sentence resumes in place rather than restarting.
- [ ] Send a turn from Telegram while a browser turn is generating. The second is refused
      with the busy sentence, and neither story is corrupted.
- [ ] On a phone: the menu opens upward and the keyboard does not cover it.

## Tests the epic adds

- The three routes: happy path, a 409 on a retired session, and a 409 with the service's own text
  when Retry is not available.
- The lock: a second generation on the same session is refused while the first is running, and two
  different sessions are not blocked by each other.
- The optimistic path: the player's message appears before the response resolves; a failure leaves
  an error row and keeps the typed text.
- Stick-to-bottom: following appends and scrolls; reading appends and does not scroll, and raises
  the pill count.
- The split button: the draft is untouched by Continue and by Retry; Retry is disabled with a
  reason when the last message is the player's; the Continue label follows the truncation flag.

## Deviations from the plan above

Four, all deliberate.

1. **The pending turn rides *beside* `transcript`, not inside it.** The scope said to push
   the player's message into `transcript` and replace it later. `transcript` is the server's
   list, and everything reading it — the delete-last button, the per-turn trace lookup —
   treats every entry as real and stored. A `pendingTurn` field costs one extra piece of
   state; the alternative costs every reader a way to tell real rows from provisional ones.
2. **`LLMError` becomes a 502.** The scope named only the 409 cases. Without this a model
   that is down returns a bare 500 with no body, and the pending row has nothing to show.
3. **`isGenerating` is a getter, not an action.** It is derived state and belongs with the
   other derived state.
4. **`pinia` joined `optimizeDeps.include` in `vite.config.ts`.** The store test is the
   first test to build a store, and discovering Pinia mid-run drops the active instance and
   fails every test in the file. The config already pre-bundles `zod` for exactly this
   reason. Caught as a flake — a failing run followed by a passing one — not as a clean
   failure.

## Out of scope

- **Starting a new story from the panel.** Play what already exists first. Adding a scenario
  picker and the persona form is the natural follow-up epic, and it is a clean slice on its own.
- **Streaming and cancel — one backlog card, not two.** Both need the same switch from
  `respond()` ([provider.py:116](../../src/rp_engine/infrastructure/llm/lmstudio/provider.py#L116))
  to `respond_stream()`, because cancelling needs the `PredictionStream` handle that only the
  streaming call returns. Today the call runs inside `asyncio.to_thread`
  ([:70](../../src/rp_engine/infrastructure/llm/lmstudio/provider.py#L70)) and a Python thread
  cannot be stopped from outside. A browser that gives up waiting leaves the model generating to
  the end, with the next turn queued behind it. Streaming also changes the shape of
  `LLMProvider.generate`, which promises a finished reply, so it needs an ADR and a check of every
  reader of that promise: `ChatService`, the memory pipeline, the trace record, and the S027
  length recovery. Nothing in this epic blocks it. The pending row from step 3 is already the
  shape the streamed text will fill, and Cancel becomes Send's state during a generation rather
  than a fourth control.
- **Rules, language, director notes and the memory switch as play controls.** They stay read-and-
  edit inside their panels. They are where the split button's menu grows next.
- **Restart and clear.** They destroy state and the panel already has delete.
- **Authentication.** One operator, one tailnet. Roles are an abstraction maintained alone forever.

## Open questions

- **Retry rewrites the whole conversation.** It clears the stored messages and writes every one
  back minus the dropped reply ([chat_service.py:361](../../src/rp_engine/application/services/chat_service.py#L361)).
  On Telegram retries are rare. Behind a button, on a story hundreds of messages long, that cost
  gets paid often. Worth measuring after this epic; not worth fixing inside it.
- **Retry spends a queued director note.** `_consume_director_instruction` runs on the retry like
  any other generation. Correct today, and easy to trigger by accident when the two controls sit
  next to each other. It may want a warning in the menu.
- **The `···` and the desktop.** Behind one control is right on a phone. On a wide screen there is
  room to leave the filters visible. Not worth two layouts for one operator, so it stays hidden on
  both until it annoys someone.
