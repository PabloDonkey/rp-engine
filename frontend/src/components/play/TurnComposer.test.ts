import { defineComponent, h, ref } from "vue";
import { userEvent } from "vitest/browser";
import { expect, test, vi } from "vitest";
import { render } from "vitest-browser-vue";

import TurnComposer from "@/components/play/TurnComposer.vue";

type Props = {
  generating?: boolean;
  disabled?: boolean;
  canRetry?: boolean;
  finishesReply?: boolean;
  retryReason?: string;
};

function mount(props: Props = {}, handlers: Record<string, () => void> = {}) {
  return render(TurnComposer, {
    props: {
      generating: false,
      canRetry: true,
      finishesReply: false,
      ...props,
      ...handlers,
    },
  });
}

/** A parent that actually owns the draft, so `v-model` round-trips like it does in the page. */
function mountBound(props: Props = {}, handlers: Record<string, () => void> = {}) {
  const draft = ref("half a reply");
  const Harness = defineComponent({
    render() {
      return h(TurnComposer, {
        modelValue: draft.value,
        "onUpdate:modelValue": (value: string) => (draft.value = value),
        generating: false,
        canRetry: true,
        finishesReply: false,
        ...props,
        ...handlers,
      });
    },
  });
  return { screen: render(Harness), draft };
}

test("Send is off until something is typed", async () => {
  const screen = mount();

  await expect.element(screen.getByRole("button", { name: "Send" })).toBeDisabled();

  await screen.getByRole("textbox").fill("I climb the stairs");

  await expect.element(screen.getByRole("button", { name: "Send" })).toBeEnabled();
});

test("Continue leaves the draft alone", async () => {
  // The worst bug this pattern invites: a menu item that silently eats what you typed.
  const onContinueStory = vi.fn();
  const { screen, draft } = mountBound({}, { onContinueStory });

  await screen.getByRole("button", { name: "More turn actions" }).click();
  await screen.getByRole("menuitem", { name: /Continue/ }).click();

  expect(onContinueStory).toHaveBeenCalledOnce();
  expect(draft.value).toBe("half a reply");
  await expect.element(screen.getByRole("textbox")).toHaveValue("half a reply");
});

test("Retry leaves the draft alone", async () => {
  const onRetry = vi.fn();
  const { screen, draft } = mountBound({}, { onRetry });

  await screen.getByRole("button", { name: "More turn actions" }).click();
  await screen.getByRole("menuitem", { name: /Retry/ }).click();

  expect(onRetry).toHaveBeenCalledOnce();
  expect(draft.value).toBe("half a reply");
});

test("Retry is greyed with its reason when the last message is the player's", async () => {
  // Greyed, not hidden: hiding it changes the menu's height between openings, so the item
  // you were reaching for moves under your finger.
  const onRetry = vi.fn();
  const screen = mount(
    { canRetry: false, retryReason: "the last message is not a narrator reply" },
    { onRetry },
  );

  await screen.getByRole("button", { name: "More turn actions" }).click();

  const retry = screen.getByRole("menuitem", { name: /Retry/ });
  await expect.element(retry).toBeVisible();
  await expect.element(retry).toBeDisabled();
  await expect
    .element(screen.getByText("the last message is not a narrator reply"))
    .toBeVisible();
});

test("Continue says 'Finish reply' when the last turn was cut off", async () => {
  const screen = mount({ finishesReply: true });

  await screen.getByRole("button", { name: "More turn actions" }).click();

  await expect.element(screen.getByRole("menuitem", { name: /Finish reply/ })).toBeVisible();
});

test("Continue says 'Continue' when the last turn ended on its own", async () => {
  const screen = mount({ finishesReply: false });

  await screen.getByRole("button", { name: "More turn actions" }).click();

  await expect.element(screen.getByRole("menuitem", { name: /Continue/ })).toBeVisible();
});

test("Escape closes the menu and puts focus back on the trigger", async () => {
  // Losing focus to the document body after Escape strands a keyboard user with nothing
  // selected, which is worse than never having opened the menu.
  const screen = mount();
  const trigger = screen.getByRole("button", { name: "More turn actions" });

  await trigger.click();
  await expect.element(screen.getByRole("menu")).toBeVisible();

  await userEvent.keyboard("{Escape}");

  await expect.element(screen.getByRole("menu")).not.toBeInTheDocument();
  await expect.element(trigger).toHaveFocus();
});

test("the arrow keys open the menu from the trigger", async () => {
  const screen = mount();

  await screen.getByRole("button", { name: "More turn actions" }).element().focus();
  await userEvent.keyboard("{ArrowDown}");

  await expect.element(screen.getByRole("menu")).toBeVisible();
  await expect.element(screen.getByRole("menuitem", { name: /Continue/ })).toHaveFocus();
});

test("everything is off while a turn is generating", async () => {
  const screen = mount({ generating: true });

  await expect.element(screen.getByRole("textbox")).toBeDisabled();
  await expect.element(screen.getByRole("button", { name: "Writing…" })).toBeDisabled();
});

test("a retired story cannot be typed into", async () => {
  const screen = mount({ disabled: true });

  await expect.element(screen.getByRole("textbox")).toBeDisabled();
  await expect.element(screen.getByRole("button", { name: "More turn actions" })).toBeDisabled();
});
