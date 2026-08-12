<script setup lang="ts">
import { ref } from "vue";

/**
 * A list of short values, as chips.
 *
 * Unlike `StringListField`, order carries no meaning here, so there is no reorder control.
 * This is for `tags`-style metadata, where each value is a word or two.
 */
const props = withDefaults(defineProps<{ label: string; placeholder?: string }>(), {
  placeholder: "Type and press Enter",
});

const tags = defineModel<string[]>({ required: true });
const draft = ref("");

function commit(): void {
  const text = draft.value.trim();
  draft.value = "";
  // A blank entry and a repeat both add nothing, and both are easy to do by accident.
  if (!text || tags.value.includes(text)) return;
  tags.value = [...tags.value, text];
}

function remove(tag: string): void {
  tags.value = tags.value.filter((item) => item !== tag);
}

function onBackspace(): void {
  // Only when the box is already empty, so backspace never eats a tag mid-word.
  if (draft.value !== "" || tags.value.length === 0) return;
  tags.value = tags.value.slice(0, -1);
}
</script>

<template>
  <div class="grid gap-1">
    <div v-if="tags.length" class="flex flex-wrap gap-1">
      <span
        v-for="tag in tags"
        :key="tag"
        class="flex items-center gap-1 rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/10"
      >
        {{ tag }}
        <button
          type="button"
          :aria-label="`Remove ${tag}`"
          class="text-neutral-500"
          @click="remove(tag)"
        >
          &times;
        </button>
      </span>
    </div>
    <input
      v-model="draft"
      type="text"
      :aria-label="props.label"
      :placeholder="placeholder"
      class="rounded-md border border-black/10 bg-transparent px-2 py-1.5 dark:border-white/10"
      @keydown.enter.prevent="commit"
      @keydown.delete="onBackspace"
      @blur="commit"
    />
  </div>
</template>
