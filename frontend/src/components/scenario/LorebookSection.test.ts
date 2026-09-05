import { beforeEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-vue";

import LorebookSection from "@/components/scenario/LorebookSection.vue";
import type { LoreEntry } from "@/api";

const accident: LoreEntry = {
  id: "11111111-1111-4111-8111-111111111111",
  scenario_definition_id: "jane-butcher-shop",
  title: "The Accident",
  content: "Jane once used more force than she meant to.",
  trigger_keys: ["hurting someone", "childhood"],
  priority: "high",
  related_entry_ids: [],
  created_at: "2026-09-03T00:00:00Z",
  updated_at: "2026-09-03T00:00:00Z",
};

const friendship: LoreEntry = {
  ...accident,
  id: "22222222-2222-4222-8222-222222222222",
  title: "The Lost Friendship",
  content: "The trust never came back.",
  trigger_keys: ["old friend"],
  priority: "normal",
};

const listLorebookEntries = vi.fn(async () => [] as LoreEntry[]);
const createLoreEntry = vi.fn(async () => accident);
const updateLoreEntry = vi.fn(async () => accident);
const deleteLoreEntry = vi.fn(async () => undefined);

vi.mock("@/api", () => ({
  listLorebookEntries: (...args: unknown[]) => listLorebookEntries(...args),
  createLoreEntry: (...args: unknown[]) => createLoreEntry(...args),
  updateLoreEntry: (...args: unknown[]) => updateLoreEntry(...args),
  deleteLoreEntry: (...args: unknown[]) => deleteLoreEntry(...args),
}));

// Each test sets its own list result explicitly, so a leftover queued
// `mockResolvedValueOnce` from a previous test can never leak into the next one.
beforeEach(() => {
  listLorebookEntries.mockReset().mockResolvedValue([]);
  createLoreEntry.mockReset().mockResolvedValue(accident);
  updateLoreEntry.mockReset().mockResolvedValue(accident);
  deleteLoreEntry.mockReset().mockResolvedValue(undefined);
});

test("lists an entry's title and trigger keys, but never its id", async () => {
  listLorebookEntries.mockResolvedValue([accident]);
  const screen = render(LorebookSection, { props: { scenarioId: "jane-butcher-shop" } });

  await expect.element(screen.getByText("The Accident")).toBeVisible();
  await expect.element(screen.getByText("hurting someone")).toBeVisible();
  // The id is a generated UUID nobody should have to read.
  await expect.element(screen.getByText(accident.id)).not.toBeInTheDocument();
});

test("an empty scenario says so instead of showing a blank list", async () => {
  listLorebookEntries.mockResolvedValueOnce([]);
  const screen = render(LorebookSection, { props: { scenarioId: "empty-scenario" } });

  await expect.element(screen.getByText("No lore entries yet.")).toBeVisible();
});

test("creating an entry asks for no id, sends the typed fields, and refreshes the list", async () => {
  listLorebookEntries.mockResolvedValueOnce([]).mockResolvedValueOnce([accident]);
  const screen = render(LorebookSection, { props: { scenarioId: "jane-butcher-shop" } });
  await expect.element(screen.getByText("No lore entries yet.")).toBeVisible();

  await screen.getByRole("button", { name: "New entry" }).click();
  await expect.element(screen.getByLabelText("Entry id")).not.toBeInTheDocument();
  await expect.element(screen.getByText("Trigger keys")).toBeVisible();
  await expect.element(screen.getByText("Priority")).not.toBeInTheDocument();
  await screen.getByLabelText("Title").fill("The Accident");
  await screen.getByLabelText("Content").fill("Jane once used more force than she meant to.");
  await screen.getByRole("button", { name: "Create" }).click();

  await expect.element(screen.getByText("The Accident")).toBeVisible();
  expect(createLoreEntry).toHaveBeenCalledWith(
    "jane-butcher-shop",
    expect.objectContaining({
      title: "The Accident",
      content: "Jane once used more force than she meant to.",
    }),
  );
});

test("picking a related entry by title sends its id, not its title", async () => {
  listLorebookEntries.mockResolvedValue([accident, friendship]);
  const screen = render(LorebookSection, { props: { scenarioId: "jane-butcher-shop" } });
  await expect.element(screen.getByText("The Accident")).toBeVisible();

  // accident is listed first, so its own "Edit" button is the first one on the page.
  await screen.getByRole("button", { name: "Edit" }).first().click();
  // Its own title never appears as a checkbox — only entries it isn't already.
  await expect
    .element(screen.getByRole("checkbox", { name: "The Accident" }))
    .not.toBeInTheDocument();
  await screen.getByRole("checkbox", { name: "The Lost Friendship" }).click();
  await screen.getByRole("button", { name: "Save" }).click();

  expect(updateLoreEntry).toHaveBeenCalledWith(
    "jane-butcher-shop",
    accident.id,
    expect.objectContaining({ relatedEntryIds: [friendship.id] }),
  );
});

test("deleting an entry asks for confirmation first", async () => {
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  listLorebookEntries.mockResolvedValueOnce([accident]).mockResolvedValueOnce([]);
  const screen = render(LorebookSection, { props: { scenarioId: "jane-butcher-shop" } });
  await expect.element(screen.getByText("The Accident")).toBeVisible();

  await screen.getByRole("button", { name: "Delete" }).click();

  expect(confirmSpy).toHaveBeenCalled();
  expect(deleteLoreEntry).toHaveBeenCalledWith("jane-butcher-shop", accident.id);
  confirmSpy.mockRestore();
});

test("declining the confirmation leaves the entry in place", async () => {
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  listLorebookEntries.mockResolvedValueOnce([accident]);
  const screen = render(LorebookSection, { props: { scenarioId: "jane-butcher-shop" } });
  await expect.element(screen.getByText("The Accident")).toBeVisible();

  await screen.getByRole("button", { name: "Delete" }).click();

  expect(deleteLoreEntry).not.toHaveBeenCalled();
  confirmSpy.mockRestore();
});
