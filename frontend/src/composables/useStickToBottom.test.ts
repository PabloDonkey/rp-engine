import { defineComponent, h, nextTick, ref } from "vue";
import { expect, test } from "vitest";
import { render } from "vitest-browser-vue";

import { useStickToBottom } from "@/composables/useStickToBottom";

/** A short scroll box holding tall rows, so the content really overflows in the browser. */
function harness(initialRows = 8) {
  const rows = ref<number[]>(Array.from({ length: initialRows }, (_, i) => i + 1));
  const el = ref<HTMLElement | null>(null);
  let api!: ReturnType<typeof useStickToBottom>;

  const Harness = defineComponent({
    setup() {
      api = useStickToBottom(el);
      return () =>
        h(
          "div",
          { ref: el, style: "height: 120px; overflow-y: auto;" },
          rows.value.map((n) =>
            h("p", { key: n, style: "height: 60px; margin: 0;" }, `turn ${n}`),
          ),
        );
    },
  });

  render(Harness);

  /** Add a row the way the page does: measure first, change, then settle. */
  async function addRow(): Promise<void> {
    const wasFollowing = api.measure();
    rows.value.push(rows.value.length + 1);
    await nextTick();
    await api.settle(wasFollowing);
  }

  return {
    get el() {
      return el.value!;
    },
    get api() {
      return api;
    },
    addRow,
  };
}

function distanceFromBottom(el: HTMLElement): number {
  return el.scrollHeight - el.scrollTop - el.clientHeight;
}

test("a new turn scrolls in while you are at the bottom", async () => {
  const h1 = harness();
  await h1.api.scrollToBottom();

  await h1.addRow();

  expect(distanceFromBottom(h1.el)).toBeLessThanOrEqual(1);
  expect(h1.api.unseen.value).toBe(0);
});

test("a new turn does not move the view while you are reading back", async () => {
  // The whole point. Yanking the page down mid-sentence is the behaviour this replaces.
  const h1 = harness();
  h1.el.scrollTop = 0;
  await nextTick();

  await h1.addRow();

  expect(h1.el.scrollTop).toBe(0);
  expect(h1.api.unseen.value).toBe(1);
});

test("unseen turns accumulate while you stay away", async () => {
  const h1 = harness();
  h1.el.scrollTop = 0;
  await nextTick();

  await h1.addRow();
  await h1.addRow();

  expect(h1.api.unseen.value).toBe(2);
});

test("jumping to the latest turn clears the count", async () => {
  const h1 = harness();
  h1.el.scrollTop = 0;
  await nextTick();
  await h1.addRow();
  expect(h1.api.unseen.value).toBe(1);

  await h1.api.scrollToBottom();

  expect(h1.api.unseen.value).toBe(0);
  expect(distanceFromBottom(h1.el)).toBeLessThanOrEqual(1);
});

test("scrolling back down on your own counts as following again", async () => {
  const h1 = harness();
  h1.el.scrollTop = 0;
  await nextTick();
  await h1.addRow();

  h1.el.scrollTop = h1.el.scrollHeight;
  // The listener is passive, so give the browser a frame to deliver the scroll event.
  await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));

  expect(h1.api.following.value).toBe(true);
  expect(h1.api.unseen.value).toBe(0);
});
