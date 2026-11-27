import { ref } from "vue";

/** The detail the server sends when speech is switched off. */
export const SPEECH_NOT_ENABLED_DETAIL = "Speech is not enabled";

/**
 * Whether the server can read messages aloud. Every play button shares it, so the first
 * "Speech is not enabled" answer hides them all. It resets when the page reloads: speech is
 * switched on or off in the server settings, not while the page is open.
 */
export const speechAvailable = ref(true);

export function markSpeechUnavailable(): void {
  speechAvailable.value = false;
}

/** For tests: put the shared state back to its start. */
export function resetSpeechAvailability(): void {
  speechAvailable.value = true;
}
