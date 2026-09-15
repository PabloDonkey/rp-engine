import { createPinia, setActivePinia } from "pinia";
import { beforeEach, expect, test, vi } from "vitest";

import { useAdminStore } from "@/stores/admin";

const startSession = vi.fn();

vi.mock("@/api", () => ({
  startSession: (...args: unknown[]) => startSession(...args),
}));

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

test("a started session is handed back and no error is left behind", async () => {
  const store = useAdminStore();
  startSession.mockResolvedValue({
    session: { id: "s1" },
    opening: "You wake.",
    resumed: false,
  });

  const started = await store.startSession("u1", "vault", "Sera Vane", "A wary courier.");

  expect(started).toEqual({
    session: { id: "s1" },
    opening: "You wake.",
    resumed: false,
  });
  expect(store.startSessionError).toBeNull();
  expect(store.startSessionBusy).toBe(false);
  expect(startSession).toHaveBeenCalledWith("u1", "vault", "Sera Vane", "A wary courier.");
});

test("a failed start reports its reason and returns null", async () => {
  const store = useAdminStore();
  startSession.mockRejectedValue(new Error("Scenario not found"));

  const started = await store.startSession("u1", "nope", "", "");

  expect(started).toBeNull();
  expect(store.startSessionError).toBe("Scenario not found");
  expect(store.startSessionBusy).toBe(false);
});
