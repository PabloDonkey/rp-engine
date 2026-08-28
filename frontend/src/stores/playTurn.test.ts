import { createPinia, setActivePinia } from "pinia";
import { beforeEach, expect, test, vi } from "vitest";

import { useAdminStore } from "@/stores/admin";

const sendTurn = vi.fn();
const continueStory = vi.fn();
const retryTurn = vi.fn();
const getSessionTranscript = vi.fn(async () => []);

vi.mock("@/api", () => ({
  sendTurn: (...args: unknown[]) => sendTurn(...args),
  continueStory: (...args: unknown[]) => continueStory(...args),
  retryTurn: (...args: unknown[]) => retryTurn(...args),
  // `runTurn` re-reads the session on success: the server is the authority on what the
  // transcript now holds, and Retry replaces a message rather than adding one.
  getSession: async () => ({ id: "s1", deleted_at: null }),
  getSessionTranscript: () => getSessionTranscript(),
  getSessionTraces: async () => [],
  getSessionMemory: async () => null,
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  getSessionTranscript.mockResolvedValue([]);
});

test("the player's line is on screen before the reply comes back", async () => {
  // A reply takes tens of seconds. Without this the page looks broken for all of them.
  const store = useAdminStore();
  const pending = deferred<unknown>();
  sendTurn.mockReturnValue(pending.promise);

  const inFlight = store.playTurn("s1", "I climb the stairs");

  expect(store.pendingTurn).toEqual({
    action: "turn",
    message: "I climb the stairs",
    error: null,
  });
  expect(store.isGenerating).toBe(true);

  pending.resolve({ role: "character", content: "…", metadata: {} });
  await inFlight;

  expect(store.pendingTurn).toBeNull();
  expect(store.isGenerating).toBe(false);
  // The transcript was re-read rather than appended to locally.
  expect(getSessionTranscript).toHaveBeenCalledOnce();
});

test("a refused turn keeps what was typed and says why", async () => {
  const store = useAdminStore();
  sendTurn.mockRejectedValue(new Error("This story is already writing a reply."));

  const ok = await store.playTurn("s1", "I climb the stairs");

  expect(ok).toBe(false);
  expect(store.pendingTurn).toEqual({
    action: "turn",
    message: "I climb the stairs",
    error: "This story is already writing a reply.",
  });
  // A pending row carrying an error is finished, not running.
  expect(store.isGenerating).toBe(false);
  expect(getSessionTranscript).not.toHaveBeenCalled();
});

test("a failed turn can be dismissed", async () => {
  const store = useAdminStore();
  sendTurn.mockRejectedValue(new Error("LM backend is unavailable."));
  await store.playTurn("s1", "hello");

  store.clearPendingTurn();

  expect(store.pendingTurn).toBeNull();
});

test("a second turn is not sent while one is running", async () => {
  const store = useAdminStore();
  const pending = deferred<unknown>();
  sendTurn.mockReturnValue(pending.promise);

  const inFlight = store.playTurn("s1", "first");
  const second = await store.playTurn("s1", "second");

  expect(second).toBe(false);
  expect(sendTurn).toHaveBeenCalledOnce();
  // The first turn is untouched by the refusal.
  expect(store.pendingTurn?.message).toBe("first");

  pending.resolve({ role: "character", content: "…", metadata: {} });
  await inFlight;
});

test("a second turn is refused while the transcript is still being re-read", async () => {
  // The reply has landed but the re-read has not. Until it does, the page still shows the
  // transcript from before the turn. Unlocking Send here would let a second turn go out
  // against a story the operator cannot see, and the server lock is already released.
  const store = useAdminStore();
  sendTurn.mockResolvedValue({ role: "character", content: "…", metadata: {} });
  const refetch = deferred<never[]>();
  getSessionTranscript.mockReturnValue(refetch.promise);

  const inFlight = store.playTurn("s1", "first");
  await vi.waitFor(() => expect(getSessionTranscript).toHaveBeenCalledOnce());

  expect(store.isGenerating).toBe(true);
  expect(await store.playTurn("s1", "second")).toBe(false);
  expect(sendTurn).toHaveBeenCalledOnce();

  refetch.resolve([]);
  await inFlight;

  expect(store.isGenerating).toBe(false);
  expect(store.pendingTurn).toBeNull();
});

test("continue and retry send no message of their own", async () => {
  const store = useAdminStore();
  const pending = deferred<unknown>();
  continueStory.mockReturnValue(pending.promise);

  const inFlight = store.playContinue("s1");

  expect(store.pendingTurn).toEqual({ action: "continue", message: null, error: null });

  pending.resolve({ role: "character", content: "…", metadata: {} });
  await inFlight;

  retryTurn.mockResolvedValue({ role: "character", content: "…", metadata: {} });
  await store.playRetry("s1");

  expect(retryTurn).toHaveBeenCalledOnce();
  expect(store.pendingTurn).toBeNull();
});
