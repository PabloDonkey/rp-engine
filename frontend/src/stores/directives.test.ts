import { createPinia, setActivePinia } from "pinia";
import { beforeEach, expect, test, vi } from "vitest";

import { useAdminStore } from "@/stores/admin";

const setSessionLanguage = vi.fn();
const addSessionRule = vi.fn();
const removeSessionRule = vi.fn();
const addSessionDirectorInstruction = vi.fn();

vi.mock("@/api", () => ({
  setSessionLanguage: (...args: unknown[]) => setSessionLanguage(...args),
  addSessionRule: (...args: unknown[]) => addSessionRule(...args),
  removeSessionRule: (...args: unknown[]) => removeSessionRule(...args),
  addSessionDirectorInstruction: (...args: unknown[]) =>
    addSessionDirectorInstruction(...args),
}));

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

test("setting the language stores the fresh session and clears any error", async () => {
  const store = useAdminStore();
  const updated = { id: "s1", directives: { language: "fr", rules: [], director_instructions: [] } };
  setSessionLanguage.mockResolvedValue(updated);

  const ok = await store.setSessionLanguage("s1", "fr");

  expect(ok).toBe(true);
  expect(store.session).toEqual(updated);
  expect(store.actionError).toBeNull();
  expect(setSessionLanguage).toHaveBeenCalledWith("s1", "fr");
});

test("an unsupported language reports its reason and leaves the session alone", async () => {
  const store = useAdminStore();
  setSessionLanguage.mockRejectedValue(new Error("Unsupported language code: xx"));

  const ok = await store.setSessionLanguage("s1", "xx");

  expect(ok).toBe(false);
  expect(store.actionError).toBe("Unsupported language code: xx");
});

test("adding a rule stores the fresh session", async () => {
  const store = useAdminStore();
  const updated = {
    id: "s1",
    directives: { language: "auto", rules: [{ id: "1", text: "No fourth-wall breaks." }] },
  };
  addSessionRule.mockResolvedValue(updated);

  const ok = await store.addSessionRule("s1", "No fourth-wall breaks.");

  expect(ok).toBe(true);
  expect(store.session).toEqual(updated);
  expect(addSessionRule).toHaveBeenCalledWith("s1", "No fourth-wall breaks.");
});

test("removing a rule stores the fresh session", async () => {
  const store = useAdminStore();
  const updated = { id: "s1", directives: { language: "auto", rules: [] } };
  removeSessionRule.mockResolvedValue(updated);

  const ok = await store.removeSessionRule("s1", "1");

  expect(ok).toBe(true);
  expect(store.session).toEqual(updated);
  expect(removeSessionRule).toHaveBeenCalledWith("s1", "1");
});

test("removing an unknown rule reports its reason", async () => {
  const store = useAdminStore();
  removeSessionRule.mockRejectedValue(new Error("No rule with id 9."));

  const ok = await store.removeSessionRule("s1", "9");

  expect(ok).toBe(false);
  expect(store.actionError).toBe("No rule with id 9.");
});

test("queuing a director note stores the fresh session", async () => {
  const store = useAdminStore();
  const updated = {
    id: "s1",
    directives: { language: "auto", rules: [], director_instructions: ["Have someone interrupt."] },
  };
  addSessionDirectorInstruction.mockResolvedValue(updated);

  const ok = await store.addSessionDirectorInstruction("s1", "Have someone interrupt.");

  expect(ok).toBe(true);
  expect(store.session).toEqual(updated);
  expect(addSessionDirectorInstruction).toHaveBeenCalledWith("s1", "Have someone interrupt.");
});
