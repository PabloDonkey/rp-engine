import { expect, test } from "vitest";
import { render } from "vitest-browser-vue";

import ScenarioForm from "@/components/scenario/ScenarioForm.vue";
import { emptyScenario } from "@/api/scenarioSchema";
import type { ScenarioDefinition } from "@/api/scenarioSchema";

function scenario(overrides: Partial<ScenarioDefinition> = {}): ScenarioDefinition {
  return { ...emptyScenario(), id: "sealed-vault", name: "The Sealed Vault", ...overrides };
}

function mount(initial: ScenarioDefinition, mode: "create" | "edit" = "edit") {
  const saved: ScenarioDefinition[] = [];
  const screen = render(ScenarioForm, {
    props: { initial, mode, onSubmit: (payload: ScenarioDefinition) => saved.push(payload) },
  });
  return { screen, saved };
}

test("the world toggle writes null when it is off, not an object of empty strings", async () => {
  // An empty world object still renders a blank world block into the prompt.
  const { screen, saved } = mount(
    scenario({
      world: { id: "w", name: "W", description: "d", rules: [], metadata: {} },
    }),
  );

  await screen.getByRole("checkbox", { name: "This scenario has a world" }).click();
  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved).toHaveLength(1);
  expect(saved[0]?.world).toBeNull();
});

test("switching the world on gives an empty world to fill in", async () => {
  const { screen } = mount(scenario({ world: null }));

  await expect
    .element(screen.getByText("No world. The prompt carries no world section."))
    .toBeVisible();

  await screen.getByRole("checkbox", { name: "This scenario has a world" }).click();

  await expect.element(screen.getByRole("textbox", { name: "World name" })).toBeVisible();
});

test("choosing RESTRICTED reveals the chat id list", async () => {
  const { screen } = mount(scenario());

  await expect.element(screen.getByText("Allowed group chat ids")).not.toBeInTheDocument();

  await screen.getByRole("radio", { name: /Restricted/ }).click();

  await expect.element(screen.getByText("Allowed group chat ids")).toBeVisible();
});

test("leaving RESTRICTED clears the chat id list from the payload", async () => {
  // Otherwise the list rides along invisibly, and comes back if the visibility does.
  const { screen, saved } = mount(
    scenario({ visibility: "RESTRICTED", allowed_group_chat_ids: ["-100123"] }),
  );

  await screen.getByRole("radio", { name: /Public/ }).click();
  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved[0]?.allowed_group_chat_ids).toEqual([]);
});

test("the id is locked when editing", async () => {
  // Changing an id would orphan every story already running the scenario.
  const { screen } = mount(scenario(), "edit");

  await expect.element(screen.getByRole("textbox", { name: "Id" })).toBeDisabled();
});

test("the id is editable and slug-checked when creating", async () => {
  const { screen, saved } = mount({ ...emptyScenario(), name: "New" }, "create");

  const idBox = screen.getByRole("textbox", { name: "Id" });
  await expect.element(idBox).toBeEnabled();

  await idBox.fill("Sealed Vault");
  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved).toHaveLength(0);
  // Twice on purpose: inline under the field, and again in the summary above the button.
  await expect.element(screen.getByText(/lowercase letters, digits/).first()).toBeVisible();
});

test("two characters sharing a role refuse to save", async () => {
  // Characters are keyed by role, so the second card would silently overwrite the first.
  const { screen, saved } = mount(
    scenario({
      characters: {
        narrator: {
          id: "a",
          name: "A",
          description: "",
          personality: "",
          greeting: "",
          metadata: {},
        },
        rival: {
          id: "b",
          name: "B",
          description: "",
          personality: "",
          greeting: "",
          metadata: {},
        },
      },
    }),
  );

  await screen.getByRole("textbox", { name: "Role" }).nth(1).fill("narrator");
  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved).toHaveLength(0);
  await expect.element(screen.getByText(/Two characters share a role/)).toBeVisible();
});

test("no characters at all is valid and means a freeform scenario", async () => {
  const { screen, saved } = mount(scenario({ characters: {} }));

  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved).toHaveLength(1);
  expect(saved[0]?.characters).toEqual({});
});

test("owner_id is always the system owner, and never on screen", async () => {
  const { screen, saved } = mount(scenario({ owner_id: "11111111-1111-1111-1111-111111111111" }));

  await expect.element(screen.getByText("Owner")).not.toBeInTheDocument();

  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved[0]?.owner_id).toBe("00000000-0000-0000-0000-000000000000");
});

test("a malformed story graph stops the save and says why", async () => {
  const { screen, saved } = mount(scenario());

  // It lives under Advanced, closed by default: it is inert data no scenario uses.
  await screen.getByText("Advanced").click();
  await screen.getByRole("textbox", { name: "Story graph JSON" }).fill("{ not json");
  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved).toHaveLength(0);
  await expect.element(screen.getByText(/Invalid JSON/)).toBeVisible();
});

test("an untouched form saves every field it was given", async () => {
  // The form builds the whole payload, so a field with no control is a field it wipes.
  const original = scenario({
    description: "A heist.",
    initial_context: "You crouch by the door.",
    rules: ["Stay in character."],
    metadata: { tags: ["noir"] },
    world: {
      id: "old-city",
      name: "The Old City",
      description: "Damp stone.",
      rules: ["Magic is rare."],
      metadata: { era: ["1920s"] },
    },
    characters: {
      narrator: {
        id: "narrator",
        name: "Narrator",
        description: "A voice.",
        personality: "Dry.",
        greeting: "Hello.",
        metadata: { age: "unknown" },
      },
    },
  });
  const { screen, saved } = mount(original);

  await screen.getByRole("button", { name: "Save" }).click();

  expect(saved[0]).toEqual(original);
});
