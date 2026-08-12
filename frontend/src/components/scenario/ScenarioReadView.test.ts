import { expect, test } from "vitest";
import { render } from "vitest-browser-vue";

import ScenarioReadView from "@/components/scenario/ScenarioReadView.vue";
import { emptyScenario } from "@/api/scenarioSchema";
import type { ScenarioDefinition } from "@/api/scenarioSchema";

function scenario(overrides: Partial<ScenarioDefinition> = {}): ScenarioDefinition {
  return {
    ...emptyScenario(),
    id: "sealed-vault",
    name: "The Sealed Vault",
    description: "A heist.",
    ...overrides,
  };
}

test("renders a list metadata value as chips and a string value as text", async () => {
  const screen = render(ScenarioReadView, {
    props: { scenario: scenario({ metadata: { genre: "heist", tags: ["noir", "crime"] } }) },
  });

  await expect.element(screen.getByText("heist", { exact: true })).toBeVisible();
  // Each list item stands on its own, not joined into one comma-soup line.
  await expect.element(screen.getByText("noir")).toBeVisible();
  await expect.element(screen.getByText("crime")).toBeVisible();
  await expect.element(screen.getByText("noir,crime")).not.toBeInTheDocument();
});

test("says plainly when there is no world, rather than showing an empty block", async () => {
  const screen = render(ScenarioReadView, { props: { scenario: scenario({ world: null }) } });

  await expect
    .element(screen.getByText("No world. The prompt carries no world section."))
    .toBeVisible();
});

test("calls a scenario with no characters freeform", async () => {
  const screen = render(ScenarioReadView, { props: { scenario: scenario() } });

  await expect
    .element(screen.getByText("No characters. This is a freeform scenario."))
    .toBeVisible();
});

test("numbers the rules, because the prompt lists them in that order", async () => {
  const screen = render(ScenarioReadView, {
    props: { scenario: scenario({ rules: ["Stay in character.", "Answer directly."] }) },
  });

  const items = screen.getByRole("listitem").elements();
  expect(items.map((item) => item.textContent)).toEqual([
    "Stay in character.",
    "Answer directly.",
  ]);
});

test("shows the allowed chat ids only when the visibility is RESTRICTED", async () => {
  const publicScreen = render(ScenarioReadView, {
    props: { scenario: scenario({ allowed_group_chat_ids: ["-100123"] }) },
  });
  await expect.element(publicScreen.getByText("Allowed group chat ids")).not.toBeInTheDocument();
  await publicScreen.unmount();

  const restricted = render(ScenarioReadView, {
    props: {
      scenario: scenario({
        visibility: "RESTRICTED",
        allowed_group_chat_ids: ["-100123"],
      }),
    },
  });
  await expect.element(restricted.getByText("Allowed group chat ids")).toBeVisible();
  await expect.element(restricted.getByText("-100123")).toBeVisible();
});

test("warns when a RESTRICTED scenario has no chat ids, because nobody can play it", async () => {
  const screen = render(ScenarioReadView, {
    props: { scenario: scenario({ visibility: "RESTRICTED", allowed_group_chat_ids: [] }) },
  });

  await expect.element(screen.getByText(/nobody can play it/)).toBeVisible();
});

test("puts the sections in the order the prompt is assembled", async () => {
  // Not a style choice: ConversationBuilder assembles description, then initial context,
  // then world, then character, then rules. Access and metadata never reach the prompt.
  const screen = render(ScenarioReadView, { props: { scenario: scenario() } });

  const headings = screen.getByRole("heading").elements();
  expect(headings.map((heading) => heading.textContent?.trim())).toEqual([
    "Description",
    "Opening scene",
    "World",
    "Characters",
    "Rules",
    "Access",
    "Metadata",
    "Story graph",
  ]);
});
