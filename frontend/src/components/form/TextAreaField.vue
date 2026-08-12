<script setup lang="ts">
import { ref } from "vue";

/**
 * Multi-line text.
 *
 * `insertions` adds chips that drop a placeholder at the cursor. The opening scene needs
 * them: `{{user}}`, `{{char}}` and `{{world}}` are easy to mistype and silently render as
 * literal text if you do.
 */
withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    error?: string | null;
    placeholder?: string;
    rows?: number;
    insertions?: readonly string[];
  }>(),
  { rows: 4, insertions: () => [] },
);

const value = defineModel<string>({ required: true });
const input = ref<HTMLTextAreaElement | null>(null);

function insert(token: string): void {
  const element = input.value;
  if (!element) {
    value.value += token;
    return;
  }
  const start = element.selectionStart ?? value.value.length;
  const end = element.selectionEnd ?? start;
  value.value = value.value.slice(0, start) + token + value.value.slice(end);
  // Put the caret after what was inserted, so typing carries on where the eye is.
  const caret = start + token.length;
  requestAnimationFrame(() => {
    element.focus();
    element.setSelectionRange(caret, caret);
  });
}
</script>

<template>
  <div class="grid gap-1">
    <label class="grid gap-1">
      <span class="text-xs text-neutral-500">{{ label }}</span>
      <textarea
        ref="input"
        v-model="value"
        :rows="rows"
        :placeholder="placeholder"
        :class="[
          'rounded-md border bg-transparent px-2 py-1.5',
          error ? 'border-red-500' : 'border-black/10 dark:border-white/10',
        ]"
      ></textarea>
    </label>
    <div v-if="insertions.length" class="flex flex-wrap items-center gap-1">
      <span class="text-xs text-neutral-500">Insert:</span>
      <button
        v-for="token in insertions"
        :key="token"
        type="button"
        class="rounded-full border border-black/10 px-2 py-0.5 font-mono text-xs dark:border-white/10"
        @click="insert(token)"
      >
        {{ token }}
      </button>
    </div>
    <span v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</span>
    <span v-else-if="hint" class="text-xs text-neutral-500">{{ hint }}</span>
  </div>
</template>
