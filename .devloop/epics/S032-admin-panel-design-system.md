# S032 · A design system for the admin panel

> **Rescoped 2026-08-29.** Written before `pablo-design-system` existed as an option; S033
> (2026-08-28) proved it out in `TurnComposer`. Two decisions, both Pablo's, both made:
> **adopt `pablo-design-system`'s tokens and primitives** rather than hand-build a parallel
> `components/ui/` (Scope sections 1 and 3 below are rewritten accordingly — extend the
> shared package where it's missing something, don't duplicate what it already has), and
> **self-host fonts via `@fontsource`**, landed already in `S032-design-system` (fonts wired
> through the package's `styles.css`, not a separate local install — see Scope section 2).
> Sections 4–6 (apply per route, dark mode, reading measure) are unchanged by the rescope.

**Status:** 🟡 IN PROGRESS — rescoped 2026-08-29, tokens+fonts wired, primitive audit underway.
**Depends on:** **S031**, which made the gap visible. Its session page is the only page with
deliberate typography, and it now looks foreign beside the other five.
**Design source:** [The Play View](https://claude.ai/code/artifact/bed99962-de97-4c5b-88d9-302fd4c2a65e)
— the mockup this is meant to match. Its palette and typeface pairing are the starting point,
not the finished answer.
**Effort:** ~3 days. Wide rather than deep: it touches every page and almost no logic.
**Risk:** Medium. No backend change and no migration, but it edits all six routes at once, so
a careless pass can break layouts nothing tests.

## Problem

The panel has no design system. It has defaults, and six pages that each guessed.

Counted, not asserted:

* **32 `<button>` elements and no button component.** At least eight distinct hand-rolled
  class strings describe what is the same control. `rounded-md border border-black/10 px-3
  py-1.5 text-sm font-medium dark:border-white/10` appears four times, a near-identical
  variant with `px-3 py-1` three times, another with `px-2 py-1` twice. Changing how a button
  looks means finding all 32.
* **33 distinct colour literals** across seven hues (amber, blue, green, neutral, red, black,
  white), written inline. There is no token layer, so "the accent" is `blue-600` in one file
  and `blue-50` in another, and nothing records that red means destructive.
* **No typeface decision anywhere.** No `@font-face`, no font link.
  [style.css](../../frontend/src/style.css) is **13 lines**: a Tailwind import, `system-ui`,
  and two `light-dark()` colours. Everything else is the browser default.
* **No type scale.** Sizes are picked per element — `text-xs`, `text-sm`, `text-[11px]`,
  `text-[15px]` — with no rule about which means what.

S031 is what exposed it. That page now sets narrator prose in a serif at a chosen size and
leading, groups its controls into chips, and uses a neutral primary button. The other five
pages do none of that, so the panel reads as two different applications.

## Goal

One visual system, defined in one place, applied to all six routes. A new page should be
assembled from parts rather than described in Tailwind strings.

## Scope

### 1. Tokens, in `@theme` — ✅ done, via adoption not authorship

`pablo-design-system/tokens.css` already defines everything this section asked for: ground /
surface / raised / hairline / muted / ink, one accent, semantic colours kept separate
(warning, danger — deliberately not "success", see gap below), a named type scale, two radii,
two shadows, all doubled for light and dark. Written once, in the package, not per-consumer —
which is the point of a shared design system. No local `@theme` block needed.

- [x] Neutrals, accent, semantic colours, type scale, radii, shadow — all present in
      `pablo-design-system/styles.css` (imported in `S032-design-system`, commit `91b5f44`).
- [ ] **Gap to confirm during the route audit:** the epic asked for "good" as a semantic
      colour; the package has `warning` and `danger` but no `success`/`good`. Check whether
      any of the 6 routes actually need one before adding it — don't invent a token nothing
      uses.
- [ ] **Gap:** no spacing scale in the package (only type scale + radii). Confirm during the
      audit whether the routes' current spacing is inconsistent enough to need one, or
      whether Tailwind's default scale is fine to keep using as-is.

### 2. Typefaces — ✅ done

Self-host via `@fontsource`, approved 2026-08-29. Landed as part of adopting the package's
full `styles.css` (`S032-design-system`, commit `91b5f44`) rather than a separate local
install — `pablo-design-system` already declares `@fontsource-variable/ibm-plex-sans`,
`@fontsource-variable/newsreader`, and `@fontsource/ibm-plex-mono` as real dependencies, and
importing its stylesheet pulls them in built.

- [x] Self-hosted, three faces, real fallback stacks — inherited from the package, not
      re-decided here.
- [ ] ~~System stacks only~~ — not needed, the yes came through.

### 3. Primitives — adopt from pablo-design-system, extend it where something is missing

Not a local `components/ui/`. `pablo-design-system` ships `PButton`, `PChip`, `PPanel`,
`PSectionLabel` already (built for S010/S031, hardened for S033's `PMenu`). Building parallel
local versions would mean maintaining two component sets for the same job — see
`pablo-design-system-workspace/AGENDA.md` for the cross-repo reasoning.

- [ ] Route audit (in progress) against the 4 existing primitives — every hand-rolled button,
      chip, panel and section-label across the 6 routes, mapped to what the primitive already
      covers vs. what it's missing.
- [ ] **Anything missing gets added to `pablo-design-system`, not hacked around locally** —
      same workflow as S033: fix upstream, test there, build, then consume. A variant
      `PButton` doesn't have yet is a `pablo-design-system` commit, not a one-off class string
      in `rp-engine`.
- [ ] The existing `components/form/` controls adopt the tokens. They do **not** get rewritten:
      `MetadataField` and `StringListField` carry tests and two bug fixes from S030, and this
      epic has no business touching that behaviour.

### 4. Apply, one route at a time

Each is its own commit, so a regression is bisectable.

- [ ] `UsersPage`
- [ ] `UserSessionsPage`
- [ ] `ScenariosPage`
- [ ] `ScenarioDetailPage`
- [ ] `ScenarioEditPage`
- [ ] `SessionDetailPage` — last, because S031 already moved it closest to the target.

### 5. Dark mode gets the same care as light

- [ ] Every token defined for both themes, never a colour that exists in one only.
- [ ] Contrast checked on both grounds, and the accent checked on both.
- [ ] The panel currently sets `color-scheme: light dark` and follows the operating system.
      Whether to add a manual toggle is **an open question below**, not scope.

### 6. Settle the reading measure

S031 removed the per-message cap so the transcript would fill the widened shell, which left
lines at roughly 110 characters. That was the right call against dead space and the wrong
number for reading long prose.

- [ ] Choose the shell width and the prose measure together, as one decision.
- [ ] If they cannot both be satisfied, prose wins inside the transcript and the freed width
      goes to the debug panels, which hold wide JSON and currently scroll sideways.

## Order of work

1. Step 1 and step 2 together — nothing else can start until the tokens and the faces exist.
2. Step 3.
3. Step 4, simplest route first, so the primitives get exercised before they reach the
   busiest page.
4. Steps 5 and 6.

## Verification

- [ ] `npm run test` green, `vue-tsc` clean, `npm run build` clean.
- [ ] **Screenshots of all six routes at three widths (390, 1024, 1440) in both themes** —
      36 renders, captured in headless Chromium with the console checked for errors. S031
      proved the point: the page was built without ever being looked at, and every fault in
      it was visible in the first screenshot.
- [ ] No page scrolls sideways at 390px.
- [ ] Keyboard focus is visible on every interactive element, in both themes.

## Tests the epic adds

Few, deliberately. This changes how things look, and a test asserting a class name locks in
the styling rather than the behaviour.

- `BaseButton`: the disabled variant does not emit a click; the danger variant is reachable
  by role and name.
- The existing 79 tests must keep passing untouched. They query by role and by visible text,
  not by class, so they should survive the migration — and if one does not, that test was
  asserting presentation and wants rewriting anyway.

## Out of scope

- **Any behaviour change.** If a page does something confusing, that is a separate epic. This
  one may not fix logic while it is repainting.
- **The form controls' internals** (`MetadataField`, `StringListField`, `ScenarioForm`). They
  take the tokens and keep their behaviour.
- **A component library.** Reka UI was considered twice during S031 and declined twice. Four
  primitives written by hand is less than one dependency, and the panel has no combobox, no
  date picker and no modal stack to justify it.
- **The Telegram surface.** Unaffected.

## Open questions

- **A manual theme toggle.** The panel follows the operating system today. A toggle needs
  somewhere to persist the choice, which means either `localStorage` or a settings row, and it
  is worth asking whether it is wanted at all before building it.
- **Whether the display face earns its place.** A serif for narrator prose is clearly right: it is a story. A display serif for page headings might just be decoration on a debugging
  tool. Try it on one page before committing all six.
- **The empty right side.** With a wide shell and a readable measure, something has to fill
  the space beside the story. A right rail holding the memory bars while playing is the
  obvious candidate, and it is also a layout change that belongs in its own epic, not here.
