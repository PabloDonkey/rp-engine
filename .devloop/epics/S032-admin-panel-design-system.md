# S032 · A design system for the admin panel

**Status:** 🟡 NOT STARTED — written 2026-08-25, nothing built.
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

### 1. Tokens, in `@theme`

Tailwind 4 takes design tokens in CSS, so they belong in `style.css` rather than a config file.

- [ ] Neutrals biased slightly toward the accent, so the greys read as chosen rather than
      inherited. Ground, surface, raised surface, hairline, muted text, body text.
- [ ] One accent, used for the primary action and nothing else.
- [ ] Semantic colours kept **separate from the accent**: destructive, warning, good. Red is
      already destructive by accident across the panel; this makes it a rule.
- [ ] A type scale with named steps, and a spacing scale. Both small enough to memorise.
- [ ] Radii and one shadow. The panel currently mixes `rounded`, `rounded-md`, `rounded-lg`
      and `rounded-full` with no logic.

### 2. Typefaces

Three roles: a display face with restraint, a body face, and a mono for labels, ids and
numbers. The panel already leans on `font-mono` for ids and `tabular-nums` for the memory
figures, so the third role exists whether or not it is named.

- [ ] Decide how they are served. **Recommendation: self-host through `@fontsource` packages.**
      The panel is reached over Tailscale and is often the only thing running; a Google Fonts
      link means an external request on every load, and a slow or blocked one leaves the page
      in a fallback face. Self-hosting costs three small dependencies. It **needs Pablo's yes**
      before anything is installed.
- [ ] The alternative, if that yes does not come: system stacks only. A system serif for
      prose, `system-ui` for the interface, `ui-monospace` for data. Free, no dependency, and
      it will not match the mockup exactly. Say so rather than pretending otherwise.
- [ ] Whatever is chosen, every face declares a real fallback stack.

### 3. Primitives in `components/ui/`

- [ ] `BaseButton` — variants primary, secondary, danger and ghost, sizes small and normal,
      disabled handled once. This alone replaces the eight class strings.
- [ ] `BaseChip` — the S031 panel chips, and the status pills on the session and scenario
      lists, are the same thing.
- [ ] `BasePanel` — the bordered card used for every block on every page.
- [ ] `SectionLabel` — the uppercase eyebrow above each section.
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
