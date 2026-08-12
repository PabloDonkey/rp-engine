import { expect, test } from "vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-vue";
import { defineComponent, h, ref } from "vue";

import MetadataField from "@/components/form/MetadataField.vue";
import type { Metadata } from "@/api/scenarioSchema";

function mount(initial: Metadata) {
  const metadata = ref<Metadata>(initial);
  const Host = defineComponent({
    setup() {
      return () =>
        h(MetadataField, {
          label: "Metadata",
          modelValue: metadata.value,
          "onUpdate:modelValue": (value: Metadata) => (metadata.value = value),
        });
    },
  });
  return { screen: render(Host), metadata };
}

test("a text row and a list row both round-trip unchanged", async () => {
  const { metadata } = mount({ genre: "heist", tags: ["noir", "crime"] });

  expect(metadata.value).toEqual({ genre: "heist", tags: ["noir", "crime"] });
});

test("switching a text row to a list splits it on commas", async () => {
  // "noir, crime" typed into a text row is almost always two values.
  const { screen, metadata } = mount({ tags: "noir, crime" });

  await screen.getByRole("button", { name: "Switch tags to list" }).click();

  expect(metadata.value).toEqual({ tags: ["noir", "crime"] });
});

test("switching a list row back to text joins it", async () => {
  const { screen, metadata } = mount({ tags: ["noir", "crime"] });

  await screen.getByRole("button", { name: "Switch tags to text" }).click();

  expect(metadata.value).toEqual({ tags: "noir, crime" });
});

test("removing a row leaves no empty key behind", async () => {
  const { screen, metadata } = mount({ genre: "heist", era: "1920s" });

  await screen.getByRole("button", { name: "Remove genre" }).click();

  expect(metadata.value).toEqual({ era: "1920s" });
  expect(Object.keys(metadata.value)).not.toContain("");
});

test("a new row with no key yet writes nothing", async () => {
  // A half-typed row is not an entry, so it must not appear as a blank key in the payload.
  const { screen, metadata } = mount({ genre: "heist" });

  await screen.getByRole("button", { name: "Add metadata" }).click();

  expect(metadata.value).toEqual({ genre: "heist" });
});

test("typing a key and a value adds the entry", async () => {
  const { screen, metadata } = mount({});

  await screen.getByRole("button", { name: "Add metadata" }).click();
  await screen.getByRole("textbox", { name: "Metadata key 1" }).fill("era");
  await screen.getByRole("textbox", { name: "Metadata value 1" }).fill("1920s");

  expect(metadata.value).toEqual({ era: "1920s" });
});

test("adding a tag to a list row keeps the other rows", async () => {
  const { screen, metadata } = mount({ genre: "heist", tags: ["noir"] });

  const tagBox = screen.getByRole("textbox", { name: "Metadata values for tags" });
  await tagBox.fill("crime");
  await userEvent.keyboard("{Enter}");

  expect(metadata.value).toEqual({ genre: "heist", tags: ["noir", "crime"] });
});
