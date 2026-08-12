import { expect, test } from "vitest";
import { render } from "vitest-browser-vue";
import { defineComponent, h, ref } from "vue";

import StringListField from "@/components/form/StringListField.vue";

/**
 * Order is load-bearing here: the prompt lists scenario rules in this order, so add,
 * remove and reorder all have to produce exactly the array the author sees.
 *
 * The wrapper holds the model, because the control is only correct when its own output is
 * fed back to it — testing it against a frozen prop would pass on a component that never
 * re-renders.
 */
function mount(initial: string[]) {
  const items = ref(initial);
  const Host = defineComponent({
    setup() {
      return () =>
        h(StringListField, {
          label: "Rule",
          modelValue: items.value,
          "onUpdate:modelValue": (value: string[]) => (items.value = value),
        });
    },
  });
  return { screen: render(Host), items };
}

test("adds an empty line, and typing fills it", async () => {
  const { screen, items } = mount([]);

  await screen.getByRole("button", { name: "Add" }).click();
  await screen.getByRole("textbox", { name: "Rule 1" }).fill("Stay in character.");

  expect(items.value).toEqual(["Stay in character."]);
});

test("removes the line that was asked for, not the last one", async () => {
  const { screen, items } = mount(["first", "second", "third"]);

  await screen.getByRole("button", { name: "Remove Rule 2" }).click();

  expect(items.value).toEqual(["first", "third"]);
});

test("moves a line down and back up, ending where it started", async () => {
  const { screen, items } = mount(["first", "second", "third"]);

  await screen.getByRole("button", { name: "Move Rule 1 down" }).click();
  expect(items.value).toEqual(["second", "first", "third"]);

  await screen.getByRole("button", { name: "Move Rule 2 up" }).click();
  expect(items.value).toEqual(["first", "second", "third"]);
});

test("cannot move the first line up or the last line down", async () => {
  const { screen } = mount(["first", "second"]);

  await expect.element(screen.getByRole("button", { name: "Move Rule 1 up" })).toBeDisabled();
  await expect.element(screen.getByRole("button", { name: "Move Rule 2 down" })).toBeDisabled();
});

test("says so when the list is empty", async () => {
  const { screen } = mount([]);

  await expect.element(screen.getByText("None yet.")).toBeVisible();
});
