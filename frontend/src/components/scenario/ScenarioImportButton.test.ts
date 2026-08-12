import { expect, test, vi } from "vitest";
import { render } from "vitest-browser-vue";

import ScenarioImportButton from "@/components/scenario/ScenarioImportButton.vue";

function jsonFile(name: string, text: string): File {
  return new File([text], name, { type: "application/json" });
}

function mount(importScenario: (payload: unknown) => Promise<{ id: string }>) {
  return render(ScenarioImportButton, { props: { importScenario } });
}

test("imports every file that was picked", async () => {
  const importScenario = vi.fn(async (payload: unknown) => ({
    id: (payload as { id: string }).id,
  }));
  const screen = mount(importScenario);

  await screen.getByLabelText("Import JSON").upload([
    jsonFile("vault.json", '{"id":"sealed-vault"}'),
    jsonFile("manor.json", '{"id":"haunted-manor"}'),
  ]);

  await expect.element(screen.getByText("Imported as sealed-vault")).toBeVisible();
  await expect.element(screen.getByText("Imported as haunted-manor")).toBeVisible();
  expect(importScenario).toHaveBeenCalledTimes(2);
});

test("one bad file does not stop the rest", async () => {
  // A batch that gives up halfway leaves you guessing which half landed.
  const importScenario = vi.fn(async (payload: unknown) => ({
    id: (payload as { id: string }).id,
  }));
  const screen = mount(importScenario);

  await screen.getByLabelText("Import JSON").upload([
    jsonFile("broken.json", "{ not json"),
    jsonFile("vault.json", '{"id":"sealed-vault"}'),
  ]);

  await expect.element(screen.getByText(/Invalid JSON/)).toBeVisible();
  await expect.element(screen.getByText("Imported as sealed-vault")).toBeVisible();
  // The broken file never reached the server.
  expect(importScenario).toHaveBeenCalledTimes(1);
});

test("reports the server's own reason when an import is refused", async () => {
  const importScenario = vi.fn(async () => {
    throw new Error("Scenario payload failed validation");
  });
  const screen = mount(importScenario);

  await screen
    .getByLabelText("Import JSON")
    .upload([jsonFile("vault.json", '{"id":"sealed-vault"}')]);

  await expect.element(screen.getByText(/Scenario payload failed validation/)).toBeVisible();
});
