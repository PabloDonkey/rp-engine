> 🗄️ **ARCHIVED — COMPLETED 2026-08-28.** Frozen; do not edit. Kept as evolution history.
> **Result:** `TurnComposer`'s `[ Send ▾ ]` menu now uses `pablo-design-system`'s `PMenu`
> instead of ~110 lines of hand-rolled dropdown logic (open state, focus management,
> arrow-key and Escape handling, an outside-click listener). This closes the cross-repo gap
> `pablo-design-system`'s S002 epic left open: **`TurnComposer.test.ts` passes unchanged**
> (10/10), the full frontend suite is green (80/80), typecheck and build are clean in both
> repos. `pablo-design-system` needed a real fix first — `PMenu`'s `DropdownMenuTrigger` was
> missing Reka UI's `as-child` prop, so a slotted custom trigger rendered as two nested
> `<button>` elements, which the browser splits into siblings — landed alongside this epic
> (`pablo-design-system@3369116`). CSS wiring pulls in only `pablo-design-system/tokens.css`,
> not the package's full `styles.css`, which also installs self-hosted webfonts and a
> body-level base layer that S032 gates on a separate yes. **The browser test runner could
> not be re-verified after the final dependency cleanup** — see Verification.

# S033 · TurnComposer adopts pablo-design-system's PMenu

**Status:** ✅ COMPLETE (2026-08-28) — one check still open, see Verification
**Effort:** ~half a day
**Risk:** Low — behaviour-preserving by construction: the acceptance gate is that
`TurnComposer.test.ts` passes with zero edits.
**Depends on:** `pablo-design-system`'s S002 epic (`PMenu`), which left a `PENDING`
integration note this epic closes. Coordinated from
`~/projects/pablo-design-system-workspace` — see its `AGENDA.md` for the cross-repo
tracking this epic grew out of.

## Problem

Two repos, one bug, one workaround. `pablo-design-system`'s S002 epic built `PMenu` to
replace the composer's hand-rolled dropdown, with a strict acceptance rule: `rp-engine`'s
`TurnComposer.test.ts` must pass **unchanged**. That integration was never done — the S002
archive carries a `PENDING: integration test with rp-engine` note an archived, frozen epic
cannot resolve by itself.

In the meantime, an AI coding assistant working in `rp-engine` alone hit the underlying bug
`PMenu` had (see below) and "fixed" it by hand-rolling a direct Reka UI `DropdownMenu` inside
`TurnComposer.vue` — a real improvement over the *previous* hand-rolled version (it now used
Reka's own keyboard handling instead of a bespoke one), but it fixed the symptom in the
consumer instead of the defect in the shared component, leaving `PMenu` itself still broken
for the next caller.

**Root cause, found this session:** `PMenu.vue`'s `<DropdownMenuTrigger>` was missing Reka
UI's `as-child` prop. Without it, Reka wraps whatever is slotted in with its own `<button>`,
so slotting in a custom trigger produces two nested `<button>` elements. Browsers cannot nest
buttons, so the DOM splits the attempt into two siblings, and any role-based query
(`getByRole("button", {name: ...})`) then matches both — the "resolved to 2 elements"
strict-mode failure.

## What changed

**`pablo-design-system`** (commit `3369116`):
- `as-child` added to `PMenu`'s `DropdownMenuTrigger` — the real fix.
- `disabled?: boolean` added to `MenuItem`, separate from `disabledReason`, for an item
  greyed out with no reason shown (`TurnComposer`'s "a turn is generating" case).
- `triggerClass` wired through (was declared, never applied).
- `PMenu.test.ts`'s slot setup was independently broken: `slots: { default: () => ({
  template: "..." }) }` returns a plain object, not a VNode, so every test that clicked
  the trigger timed out waiting for a button that was never in the DOM. Fixed to the
  plain-string / `h()` forms Vue Test Utils expects; rewritten with real role-based
  assertions, including a regression test for the exact duplication bug.
- `PChip.test.ts`: `getByRole` name matching is substring by default, so `{name: "noir"}`
  matched both the "noir" button and "Remove tag: noir". Added `exact: true`.

**`rp-engine`** (this commit):
- `TurnComposer.vue` rewritten against `PMenu`: `continue`/`retry` become `MenuItem` entries
  (`label`, `hint`, `disabled`, `disabledReason`), selection routes through one `onSelect`
  keyed by item `value`. All keyboard/focus/outside-click handling is gone — Reka provides
  it, through `PMenu`.
- `pablo-design-system` added as a dependency (`file:../../pablo-design-system`, per its
  README — not `file:../pablo-design-system`, which is one directory too shallow from
  `frontend/package.json` and silently produces a dangling symlink).
- `reka-ui` added to `vite.config.ts`'s `optimizeDeps.include` (PMenu imports it, and it's
  now only a transitive dependency — see Verification for why it is *not* a direct
  dependency here).
- `style.css` imports `pablo-design-system/tokens.css` (not the aggregate `styles.css`) plus
  the required `@source` directive — see the ⚠️ box below.

## ⚠️ A scope decision worth reading before the next cross-repo change

`pablo-design-system`'s own README documents three lines for a consumer to wire up:
`@import "tailwindcss"`, `@import "pablo-design-system/styles.css"`, `@source
"../node_modules/pablo-design-system/dist"`. Following that literally pulled in the
package's self-hosted webfonts (Newsreader, IBM Plex Sans, IBM Plex Mono — real font files,
not just declarations) and a `base.css` layer that overrides `body`'s background, text
colour, and font-family for the **whole app**. That is exactly the "self-hosted typefaces
… needs a yes before installing" gate the S032 backlog card already put on this repo, and
"one menu adopts a shared component" is not that yes.

Fixed by importing `pablo-design-system/tokens.css` alone: the CSS custom properties `PMenu`
needs (`rounded-control`, `border-hairline`, `bg-surface`, `text-ink`, `text-body`, …) with
none of the fonts or the base layer. Confirmed by build output: the full `styles.css` import
added ~350 KB of `.woff`/`.woff2` assets to `dist/`; the `tokens.css`-only import adds none,
and the built CSS shrank from 39.36 KB to 32.46 KB with it removed.

**The lesson for `pablo-design-system-workspace`'s `AGENDA.md`:** the package's own "how to
install" instructions are the *full* offer, not the *minimum* one. A narrowly-scoped
integration should default to the narrowest import (`tokens.css`, or a single primitive's
styles) and let a real design-system adoption epic (S032, for this repo) make the
all-in decision deliberately, once, with the fonts question asked directly rather than
answered as a side effect of an unrelated menu fix.

## Verification

- `pablo-design-system`: `npm test` (34/34), `npm run typecheck`, `npm run build` — all
  green, all clean.
- `rp-engine` frontend: `npm run typecheck`, `npm run build` — clean, both re-run after the
  final dependency cleanup below.
- `TurnComposer.test.ts` — **10/10, unchanged from before this epic** — and the full
  frontend suite — **80/80** — both passed clean, confirmed *before* the final cleanup step.
- **Final cleanup, not re-verified against the browser suite:** the first working version
  carried `reka-ui` as a *direct* `rp-engine` dependency (leftover from the earlier
  hand-rolled-Reka workaround this epic replaces); since `TurnComposer.vue` no longer
  imports it directly — only `PMenu` does — it was removed, leaving it resolved
  transitively through `pablo-design-system`'s own dependency on it. `npm run build`
  (which fully resolves and bundles the same import graph rollup would use in production)
  stayed green after the removal, at an identical module count and bundle size to the
  version that passed the full test suite. The browser-mode test runner itself could not be
  re-run afterward: this machine's system-wide inotify instance cap (128) was exhausted by
  other already-running processes (editor language servers, mainly), which is an environment
  constraint unrelated to this change, not a masked regression — but it means the *literal*
  10/10 + 80/80 numbers above were not reproduced against the exact final dependency set.
  **Re-run `npm test` in `frontend/` once to confirm**, before treating this as fully closed.
- No live browser check of the rendered menu (open/close animation, focus ring, token-driven
  colours) — the dev server needs the FastAPI backend and a real session, out of scope for
  this session.
