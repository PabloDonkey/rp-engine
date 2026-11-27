<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";

import { synthesizeSpeech } from "@/api";
import {
  markSpeechUnavailable,
  SPEECH_NOT_ENABLED_DETAIL,
  speechAvailable,
} from "@/composables/speechAvailability";

/**
 * Reads one message aloud. A click asks the server for audio, then plays it. A second click
 * while it plays stops it. Nothing is cached: each play asks again.
 */
const props = defineProps<{ text: string }>();

type State = "idle" | "loading" | "playing";
const state = ref<State>("idle");
const error = ref<string | null>(null);

let audio: HTMLAudioElement | null = null;
let url: string | null = null;

function release(): void {
  audio?.pause();
  audio = null;
  if (url) URL.revokeObjectURL(url);
  url = null;
  state.value = "idle";
}

async function play(): Promise<void> {
  error.value = null;
  state.value = "loading";
  try {
    const blob = await synthesizeSpeech(props.text);
    url = URL.createObjectURL(blob);
    const player = new Audio(url);
    player.onended = release;
    audio = player;
    await player.play();
    state.value = "playing";
  } catch (caught) {
    release();
    if (
      caught instanceof Error &&
      (caught as { status?: number }).status === 503 &&
      caught.message === SPEECH_NOT_ENABLED_DETAIL
    ) {
      markSpeechUnavailable();
      return;
    }
    error.value = caught instanceof Error ? caught.message : "Could not play the message";
  }
}

async function onClick(): Promise<void> {
  if (state.value === "playing") {
    release();
    return;
  }
  await play();
}

onBeforeUnmount(release);

const label = computed(
  () => ({ idle: "Play message", loading: "Loading audio", playing: "Stop" })[state.value],
);
const symbol = computed(() => ({ idle: "▶", loading: "…", playing: "■" })[state.value]);
</script>

<template>
  <span v-if="speechAvailable" class="flex items-center gap-2">
    <button
      type="button"
      :disabled="state === 'loading'"
      :aria-label="label"
      :title="label"
      class="rounded px-1.5 text-micro font-medium text-muted enabled:hover:text-ink disabled:cursor-default disabled:opacity-60"
      @click="onClick"
    >
      <span aria-hidden="true">{{ symbol }}</span>
    </button>
    <span v-if="error" role="alert" class="text-micro normal-case text-danger">{{ error }}</span>
  </span>
</template>
