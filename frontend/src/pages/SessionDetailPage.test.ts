import { defineComponent, h } from "vue";
import { createPinia, setActivePinia } from "pinia";
import { expect, test, vi } from "vitest";
import { page } from "vitest/browser";
import { render } from "vitest-browser-vue";

// Real Tailwind + the design system's tokens, exactly what `main.ts` loads for the actual
// app. Without this every class below is inert and the page just renders in plain
// document flow -- which looks like the layout bug this test exists to catch, but isn't.
import "@/style.css";
import App from "@/App.vue";
import SessionDetailPage from "@/pages/SessionDetailPage.vue";
import type { AdminMessage } from "@/api";

/**
 * Regression test for a real layout bug: `<main>` in `App.vue` had no `min-h-0`, so its
 * default `min-height: auto` let it grow to fit the page's full content height instead of
 * being capped at "viewport minus header". With a transcript longer than the viewport, the
 * whole document scrolled instead of just the transcript, and the composer ended up below
 * the fold -- invisible without scrolling the page, which a chat composer should never
 * require.
 *
 * This mounts the real `App` shell (not just `SessionDetailPage`), because the bug lived in
 * the seam between `App.vue`'s `<main>` and the page, not inside the page alone -- a test
 * that only rendered `SessionDetailPage` in a hand-sized container could stay green while
 * this exact regression came back.
 */

const session = {
  id: "s1",
  scenario_definition_id: "the-lighthouse-keeper",
  owner_kind: "telegram",
  owner_id: "u1",
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-29T10:00:00Z",
  deleted_at: null,
  message_count: 40,
  directives: { language: "en", rules: [], director_instructions: [] },
  memory: { enabled_sources: ["rolling_summary"], source_budget_shares: {} },
  user_persona_name: "Mira Vance",
  user_persona_description: null,
};

// Long enough to overflow any reasonable viewport, so the test actually exercises the
// fill-then-scroll behaviour instead of passing by coincidence on a short transcript.
const transcript: AdminMessage[] = Array.from({ length: 40 }, (_, i) => ({
  role: i % 2 === 0 ? "character" : "user",
  content: `Turn ${i} of the story, with enough words in it to take up a full line or two.`,
  metadata: { turn: String(i) },
}));

const memory = {
  settings: { enabled_sources: ["rolling_summary"], source_budget_shares: {} },
  status: {
    budget_tokens: 4000,
    high_water_tokens: 3600,
    window_tokens: 2480,
    window_messages: 24,
    stored_messages: 40,
    turns_total: 40,
    covers_through_turn: 10,
    pending_turns: 4,
    behind_turns: 0,
    pending_tokens: 800,
    fold_batch_tokens: 1200,
    summary_tokens: 300,
    summary_budget_tokens: 500,
    verbatim_turns: 10,
    whole_story_fits: false,
    fold_progress: 0.66,
  },
  summary: null,
  last_pass: null,
};

vi.mock("@/api", () => ({
  getSession: async () => session,
  getSessionTranscript: async () => transcript,
  getSessionTraces: async () => [],
  getSessionMemory: async () => memory,
  exportSession: async () => ({}),
}));

// `SessionDetailPage.vue` imports `useRouter` directly, so that half needs the module
// mock. `RouterView`/`RouterLink` in `App.vue`, though, are template globals resolved
// through *component registration* (normally done by `app.use(router)`), not through a
// script import -- mocking the module does nothing for them. They're registered below
// instead, via `global.components`, the same mechanism the real router plugin uses.
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: () => {} }),
}));

const RouterLinkStub = defineComponent({
  props: ["to"],
  setup(_props, { slots }) {
    return () => h("a", slots.default?.());
  },
});

// Stands in for the route match: renders `SessionDetailPage` directly, which is exactly
// what the real router does once `/sessions/:id` matches.
const RouterViewStub = defineComponent({
  setup() {
    return () => h(SessionDetailPage, { sessionId: "s1" });
  },
});

test("header, transcript, and composer all stay within the viewport on a long story", async () => {
  setActivePinia(createPinia());
  const screen = render(App, {
    global: {
      components: { RouterView: RouterViewStub, RouterLink: RouterLinkStub },
    },
  });

  await page.viewport(1024, 900);
  // Let the session load and the transcript mount before measuring anything.
  await expect.element(screen.getByRole("textbox")).toBeInTheDocument();
  await new Promise((r) => setTimeout(r, 200));

  const viewportHeight = 900;

  // The header (title) and the composer are the two ends of the three-section layout --
  // if either is pushed outside the viewport, the fill-then-scroll layout has broken.
  const title = screen.getByText("the-lighthouse-keeper");
  await expect.element(title).toBeVisible();
  const titleBox = await title.element().getBoundingClientRect();
  expect(titleBox.top).toBeGreaterThanOrEqual(0);
  expect(titleBox.bottom).toBeLessThanOrEqual(viewportHeight);

  const composer = document.querySelector("[data-composer]");
  expect(composer).not.toBeNull();
  const composerBox = composer!.getBoundingClientRect();
  expect(composerBox.top).toBeGreaterThan(0);
  // The whole point: with 40 turns, the composer must still end up on screen.
  expect(composerBox.bottom).toBeLessThanOrEqual(viewportHeight);

  // The document itself must not need to scroll -- if it does, the bug is back: the
  // transcript stopped absorbing the overflow and the page did instead.
  const doc = document.documentElement;
  expect(doc.scrollHeight).toBeLessThanOrEqual(doc.clientHeight + 1);

  // And the transcript's own scroll well must be the one actually doing the scrolling --
  // otherwise this test would pass for the wrong reason (e.g. a transcript short enough
  // to never need to scroll at all).
  const transcriptEl = document.querySelector("[data-testid='transcript-scroll']");
  expect(transcriptEl).not.toBeNull();
  expect(transcriptEl!.scrollHeight).toBeGreaterThan(transcriptEl!.clientHeight);
});
