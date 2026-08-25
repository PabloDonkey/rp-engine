<script setup lang="ts">
import { ref } from "vue";

/**
 * A debug block that starts closed.
 *
 * Not a mode: there is no switch and nothing to remember. The closed row still names the
 * panel's current value, so the state is readable without opening anything, which is what
 * keeps the story at the top of the page without hiding the machinery behind it.
 */
defineProps<{ title: string; summary?: string }>();

const open = ref(false);
</script>

<template>
  <div class="rounded-lg border border-black/10 dark:border-white/10">
    <button
      type="button"
      class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="text-sm font-semibold">{{ title }}</span>
      <span v-if="summary" class="truncate text-xs text-neutral-500">{{ summary }}</span>
      <span class="ml-auto shrink-0 text-xs text-neutral-400" aria-hidden="true">
        {{ open ? "▾" : "▸" }}
      </span>
    </button>
    <div v-if="open" class="border-t border-black/10 p-3 text-sm dark:border-white/10">
      <slot />
    </div>
  </div>
</template>
