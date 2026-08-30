> 🗄️ **ARCHIVED — COMPLETED 2026-08-29.** Frozen; do not edit. Kept as evolution history.
> **Result:** The session transcript and the composer's growing text field now share one
> subtle scrollbar: a thin track and thumb, no native end buttons, invisible until the
> pointer is over the transcript, and never shown at all in the composer. Built as a new
> `pablo-design-system` primitive, `PScrollArea`, over Reka UI's `ScrollArea` — a plain CSS
> `::-webkit-scrollbar` approach was tried first and abandoned (see below). Full frontend
> suite 81/81, typecheck, build clean.

# S035 · Subtle scrollbars for the transcript and composer

**Status:** ✅ COMPLETE (2026-08-29)
**Effort:** ~1 session.
**Risk:** Low for the transcript (styling + a scroll-position refactor with the layout
regression test as the safety net); the composer's height model changed (see below), covered
by the existing `TurnComposer.test.ts`, which passed unchanged.
**Cross-repo companion:** `pablo-design-system`'s S005 epic, tracked in
`~/projects/pablo-design-system-workspace/AGENDA.md`.

## The ask

Pablo wanted one shared scrollbar style for two spots: the session transcript's scroll well
and the composer's auto-growing text field. Requirements arrived in a few rounds:
"subtle, show only track and thumb" → "invisible most of the time, visible only on
hover/scroll, and that must be an option because the composer wants it always invisible."

## Why not plain CSS

The first attempt styled the native scrollbar directly (`::-webkit-scrollbar-thumb` etc.) in
`style.css`. Reverted before landing: `::-webkit-scrollbar` has no Firefox equivalent
(Firefox only has the much coarser `scrollbar-width`/`scrollbar-color`, which cannot draw a
custom track/thumb shape), so "only a track and a thumb, cross-browser" is not something a
CSS-only approach can promise.

## Why a design-system primitive, not a local component

`reka-ui` was already a dependency (S033, `PMenu`) and ships a `ScrollArea` primitive built
for exactly this: a custom track and thumb, native scrollbars hidden cross-browser by Reka
itself, visibility strategies including a hover-reveal. Two consumers in one app plus a
primitive the design system explicitly could not do well itself is the same bar S002 used
for `PMenu` — this went into `pablo-design-system` as `PScrollArea` rather than rp-engine's
own `components/`.

## What changed

**`pablo-design-system`** (S005, see its own archived epic): added `PScrollArea`, a `visible`
boolean prop (`true` — Reka's hover-reveal, the default; `false` — never rendered, still
scrolls), attrs split by hand between its root (`class`/`style`, for sizing) and its viewport
(everything else, since that is the element that actually scrolls). 50 tests, typecheck,
build clean across four commits.

**`SessionTranscript.vue`:**
- The scroll well is now `<PScrollArea>` instead of a plain `overflow-y-auto` div.
  `data-testid="transcript-scroll"` moved with it onto the *viewport* (not `PScrollArea`'s
  root) — the root's height is pinned to its child, so it never actually overflows, and the
  layout regression test in `SessionDetailPage.test.ts` (`scrollHeight > clientHeight`)
  needs the viewport to still be true. That test passed unchanged, which is the real proof.
- `useStickToBottom` needs the real scrolling element to read/drive scroll position.
  `PScrollArea` exposes it as `viewport`; `SessionTranscript.vue` mirrors that into a plain
  `ref` via `watchEffect`, since the composable's signature wants an ordinary
  `Ref<HTMLElement | null>`, not something a caller has to unwrap twice.

**`TurnComposer.vue`:**
- Wrapped in `<PScrollArea :visible="false">`. The text field itself no longer clips its own
  content (`autoGrow` sets `height` to the full `scrollHeight`, uncapped) — `PScrollArea`
  does the clipping and scrolling instead.
- **A real bug caught before it shipped:** the wrapper's height was first set via CSS
  `max-height`, which looks right and even clips visually (the root still has
  `overflow: hidden`), but does not scroll — `PScrollArea`'s viewport is `height: 100%` of
  its root, and a percentage height resolves against an *indeterminate* containing block
  (`max-height` alone, no explicit `height`) as `auto`, so the viewport just grows past the
  cap instead of tracking an overflow. Found via a throwaway visual-check test (real
  Chromium, screenshots) that actually scrolled the field and asserted `scrollTop` moved —
  a plain screenshot alone would have looked correct and shipped the bug. Fixed by computing
  the clamp in JS (`Math.min(scrollHeight, MAX_HEIGHT_PX)`) and passing it as an explicit
  pixel `height`, mirroring where the clamp used to live on the field itself. `PScrollArea`'s
  own docs and a regression test now call this out as the component's most likely misuse.

## Verification

- `pablo-design-system`: 50/50 tests, typecheck, build clean (four commits on
  `worktree-S005-scroll-area`, not yet on `main` — needs Pablo to push per this repo's
  convention).
- `rp-engine` frontend: 81/81 tests **unchanged** (`TurnComposer.test.ts` 10/10,
  `SessionDetailPage.test.ts`'s layout regression test included), typecheck, build clean.
- Manual visual check (real Chromium, 1024×900, 40-turn transcript): scrollbar absent at
  rest, a thin track-and-thumb appears on hover positioned near the current scroll offset;
  an 8-line composer draft clips with zero visible scrollbar and actually scrolls when
  driven (`scrollTop` moves, last line becomes visible).

## Follow-ups, not done here

- **Closed out 2026-08-29:** `pablo-design-system`'s branch pushed to `main` (`f784f6c`).
  `rp-engine`'s own change is up as
  [PR #7](https://github.com/PabloDonkey/rp-engine/pull/7) (draft), branch
  `worktree-subtle-scrollbars` — needs review and merge.
