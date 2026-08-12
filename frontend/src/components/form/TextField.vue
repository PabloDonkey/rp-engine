<script setup lang="ts">
/** One line of text. `locked` is for a value that exists but must not change, like an id. */
withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    error?: string | null;
    placeholder?: string;
    maxlength?: number;
    locked?: boolean;
    mono?: boolean;
  }>(),
  { locked: false, mono: false },
);

const value = defineModel<string>({ required: true });
</script>

<template>
  <label class="grid gap-1">
    <span class="text-xs text-neutral-500">{{ label }}</span>
    <input
      v-model="value"
      type="text"
      :placeholder="placeholder"
      :maxlength="maxlength"
      :disabled="locked"
      :class="[
        'rounded-md border bg-transparent px-2 py-1.5',
        mono ? 'font-mono' : '',
        locked ? 'cursor-not-allowed opacity-60' : '',
        error ? 'border-red-500' : 'border-black/10 dark:border-white/10',
      ]"
    />
    <span v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</span>
    <span v-else-if="hint" class="text-xs text-neutral-500">{{ hint }}</span>
  </label>
</template>
