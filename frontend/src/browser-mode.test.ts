import { expect, test } from "vitest";
import { render } from "vitest-browser-vue";
import { defineComponent, ref } from "vue";

/**
 * Proves the browser test setup works, before any component depends on it.
 *
 * The three things it checks are the three that break first: Vitest starts a real
 * Chromium, a Vue single-file component renders into it, and a click runs the component's
 * own reactivity. A failure here is a setup problem, not a component problem.
 */

const Counter = defineComponent({
  setup() {
    const count = ref(0);
    return { count, add: () => (count.value += 1) };
  },
  template: `<button type="button" @click="add">clicked {{ count }} times</button>`,
});

test("renders a Vue component in a real browser and reacts to a click", async () => {
  const screen = render(Counter);

  const button = screen.getByRole("button");
  await expect.element(button).toHaveTextContent("clicked 0 times");

  await button.click();

  await expect.element(button).toHaveTextContent("clicked 1 times");
});
