import { expect, test, vi, beforeEach, afterEach } from "vitest";
import { render } from "vitest-browser-vue";

import { ApiError } from "@/api";
import SpeechButton from "@/components/play/SpeechButton.vue";
import { resetSpeechAvailability } from "@/composables/speechAvailability";

const synthesizeSpeech = vi.fn();

vi.mock("@/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api")>()),
  synthesizeSpeech: (...args: unknown[]) => synthesizeSpeech(...args),
}));

/** A stand-in for `Audio`: the test decides when playback ends. */
class FakeAudio {
  static instances: FakeAudio[] = [];
  src: string;
  paused = true;
  onended: (() => void) | null = null;
  constructor(src: string) {
    this.src = src;
    FakeAudio.instances.push(this);
  }
  play(): Promise<void> {
    this.paused = false;
    return Promise.resolve();
  }
  pause(): void {
    this.paused = true;
  }
  finish(): void {
    this.paused = true;
    this.onended?.();
  }
}

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
  vi.clearAllMocks();
  FakeAudio.instances = [];
  vi.stubGlobal("Audio", FakeAudio);
  resetSpeechAvailability();
  synthesizeSpeech.mockResolvedValue(new Blob(["wav"], { type: "audio/wav" }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a click sends the message text and plays the audio", async () => {
  const screen = render(SpeechButton, { props: { text: "The door creaks." } });

  await screen.getByRole("button", { name: "Play message" }).click();

  await expect.poll(() => FakeAudio.instances.length).toBe(1);
  expect(synthesizeSpeech).toHaveBeenCalledWith("The door creaks.");
  expect(FakeAudio.instances[0].src).toMatch(/^blob:/);
  expect(FakeAudio.instances[0].paused).toBe(false);
  await expect.element(screen.getByRole("button", { name: "Stop" })).toBeVisible();
});

test("the button shows a loading state while the request runs", async () => {
  const pending = deferred<Blob>();
  synthesizeSpeech.mockReturnValue(pending.promise);
  const screen = render(SpeechButton, { props: { text: "Hello." } });

  await screen.getByRole("button", { name: "Play message" }).click();

  await expect.element(screen.getByRole("button", { name: "Loading audio" })).toBeDisabled();

  pending.resolve(new Blob(["wav"]));

  await expect.element(screen.getByRole("button", { name: "Stop" })).toBeEnabled();
});

test("a second click on the playing message stops it", async () => {
  const screen = render(SpeechButton, { props: { text: "Hello." } });
  await screen.getByRole("button", { name: "Play message" }).click();
  await expect.element(screen.getByRole("button", { name: "Stop" })).toBeVisible();

  await screen.getByRole("button", { name: "Stop" }).click();

  expect(FakeAudio.instances[0].paused).toBe(true);
  await expect.element(screen.getByRole("button", { name: "Play message" })).toBeVisible();
});

test("the button goes back to Play when the audio ends", async () => {
  const screen = render(SpeechButton, { props: { text: "Hello." } });
  await screen.getByRole("button", { name: "Play message" }).click();
  await expect.element(screen.getByRole("button", { name: "Stop" })).toBeVisible();

  FakeAudio.instances[0].finish();

  await expect.element(screen.getByRole("button", { name: "Play message" })).toBeVisible();
});

test("a failed request shows the detail from the server", async () => {
  synthesizeSpeech.mockRejectedValue(new ApiError(503, "Not enough graphics card memory"));
  const screen = render(SpeechButton, { props: { text: "Hello." } });

  await screen.getByRole("button", { name: "Play message" }).click();

  await expect.element(screen.getByRole("alert")).toHaveTextContent(
    "Not enough graphics card memory",
  );
  // The button stays, so the reader can try again.
  await expect.element(screen.getByRole("button", { name: "Play message" })).toBeEnabled();
});

test("the error goes away on the next try", async () => {
  synthesizeSpeech.mockRejectedValueOnce(new ApiError(500, "Boom"));
  const screen = render(SpeechButton, { props: { text: "Hello." } });
  await screen.getByRole("button", { name: "Play message" }).click();
  await expect.element(screen.getByRole("alert")).toBeVisible();

  await screen.getByRole("button", { name: "Play message" }).click();

  await expect.element(screen.getByRole("button", { name: "Stop" })).toBeVisible();
  expect(screen.container.querySelector("[role=alert]")).toBeNull();
});

test("the button is hidden after the server says speech is not enabled", async () => {
  synthesizeSpeech.mockRejectedValue(new ApiError(503, "Speech is not enabled"));
  const screen = render(SpeechButton, { props: { text: "Hello." } });

  await screen.getByRole("button", { name: "Play message" }).click();

  await expect
    .poll(() => screen.container.querySelector("button"))
    .toBeNull();
});

test("a new button stays hidden for the rest of the page life", async () => {
  synthesizeSpeech.mockRejectedValue(new ApiError(503, "Speech is not enabled"));
  const first = render(SpeechButton, { props: { text: "Hello." } });
  await first.getByRole("button", { name: "Play message" }).click();
  await expect.poll(() => first.container.querySelector("button")).toBeNull();

  const second = render(SpeechButton, { props: { text: "Again." } });

  expect(second.container.querySelector("button")).toBeNull();
});

test("a not-enough-memory error does not hide the button", async () => {
  synthesizeSpeech.mockRejectedValue(new ApiError(503, "Not enough graphics card memory"));
  const first = render(SpeechButton, { props: { text: "Hello." } });
  await first.getByRole("button", { name: "Play message" }).click();
  await expect.element(first.getByRole("alert")).toBeVisible();

  const second = render(SpeechButton, { props: { text: "Again." } });

  await expect.element(second.getByRole("button", { name: "Play message" })).toBeVisible();
});
