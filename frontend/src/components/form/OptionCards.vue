<script setup lang="ts">
/**
 * A radio group where each choice states its own effect.
 *
 * Used for visibility, where the names alone do not say what they do — nothing on the old
 * screen explained what UNLISTED meant.
 */
defineProps<{
  label: string;
  name: string;
  options: readonly { value: string; label: string; description: string }[];
}>();

const selected = defineModel<string>({ required: true });
</script>

<template>
  <fieldset class="grid gap-2">
    <legend class="mb-1 text-xs text-neutral-500">{{ label }}</legend>
    <label
      v-for="option in options"
      :key="option.value"
      :class="[
        'flex cursor-pointer items-start gap-2 rounded-lg border p-2',
        selected === option.value
          ? 'border-neutral-900 dark:border-neutral-100'
          : 'border-black/10 dark:border-white/10',
      ]"
    >
      <input
        v-model="selected"
        type="radio"
        :name="name"
        :value="option.value"
        class="mt-1"
      />
      <span class="grid gap-0.5">
        <span class="font-medium">{{ option.label }}</span>
        <span class="text-xs text-neutral-500">{{ option.description }}</span>
      </span>
    </label>
  </fieldset>
</template>
