import { createPinia, setActivePinia } from "pinia";
import { beforeEach, expect, test } from "vitest";
import { render } from "vitest-browser-vue";

import type { AdminMessage } from "@/api";
import SessionTranscript from "@/components/play/SessionTranscript.vue";
import { resetSpeechAvailability } from "@/composables/speechAvailability";
import { useAdminStore } from "@/stores/admin";

function message(role: string, content: string): AdminMessage {
  return { role, content, metadata: {} } as AdminMessage;
}

beforeEach(() => {
  resetSpeechAvailability();
});

test("only the narrator's messages get a play button", async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useAdminStore();
  store.transcript = [
    message("character", "The door creaks open."),
    message("user", "I step inside."),
    message("character", "Dust falls from the ceiling."),
  ];

  const screen = render(SessionTranscript, {
    props: { sessionId: "s1" },
    global: { plugins: [pinia] },
  });

  await expect.element(screen.getByText("The door creaks open.")).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Play message" })).toHaveLength(2);
});

test("a transcript with only the player's lines has no play button", async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useAdminStore();
  store.transcript = [message("user", "I step inside.")];

  const screen = render(SessionTranscript, {
    props: { sessionId: "s1" },
    global: { plugins: [pinia] },
  });

  await expect.element(screen.getByText("I step inside.")).toBeVisible();
  expect(screen.container.querySelector('button[aria-label="Play message"]')).toBeNull();
});
