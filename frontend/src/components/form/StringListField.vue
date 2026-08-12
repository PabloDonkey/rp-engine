<script setup lang="ts">
/**
 * An ordered list of lines.
 *
 * Order is load-bearing for scenario rules — the prompt lists them in this order — so the
 * control shows the position and offers move up and move down. Without that, reordering
 * means deleting and retyping, and people stop doing it.
 */
withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    placeholder?: string;
    addLabel?: string;
    numbered?: boolean;
  }>(),
  { addLabel: "Add", numbered: true },
);

const items = defineModel<string[]>({ required: true });

function add(): void {
  items.value = [...items.value, ""];
}

function remove(index: number): void {
  items.value = items.value.filter((_, position) => position !== index);
}

function move(index: number, offset: number): void {
  const target = index + offset;
  if (target < 0 || target >= items.value.length) return;
  const next = [...items.value];
  const [moved] = next.splice(index, 1);
  next.splice(target, 0, moved as string);
  items.value = next;
}

function update(index: number, text: string): void {
  items.value = items.value.map((item, position) => (position === index ? text : item));
}
</script>

<template>
  <div class="grid gap-2">
    <span class="text-xs text-neutral-500">{{ label }}</span>
    <p v-if="hint" class="text-xs text-neutral-500">{{ hint }}</p>
    <p v-if="items.length === 0" class="text-xs text-neutral-500">None yet.</p>
    <div v-for="(item, index) in items" :key="index" class="flex items-center gap-1">
      <span v-if="numbered" class="w-5 shrink-0 text-right text-xs text-neutral-500">
        {{ index + 1 }}.
      </span>
      <input
        type="text"
        :value="item"
        :placeholder="placeholder"
        :aria-label="`${label} ${index + 1}`"
        class="min-w-0 flex-1 rounded-md border border-black/10 bg-transparent px-2 py-1.5 dark:border-white/10"
        @input="update(index, ($event.target as HTMLInputElement).value)"
      />
      <button
        type="button"
        :aria-label="`Move ${label} ${index + 1} up`"
        :disabled="index === 0"
        class="rounded-md border border-black/10 px-2 py-1 text-xs disabled:opacity-30 dark:border-white/10"
        @click="move(index, -1)"
      >
        &uarr;
      </button>
      <button
        type="button"
        :aria-label="`Move ${label} ${index + 1} down`"
        :disabled="index === items.length - 1"
        class="rounded-md border border-black/10 px-2 py-1 text-xs disabled:opacity-30 dark:border-white/10"
        @click="move(index, 1)"
      >
        &darr;
      </button>
      <button
        type="button"
        :aria-label="`Remove ${label} ${index + 1}`"
        class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
        @click="remove(index)"
      >
        &times;
      </button>
    </div>
    <div>
      <button
        type="button"
        class="rounded-md border border-black/10 px-3 py-1 text-xs font-medium dark:border-white/10"
        @click="add"
      >
        {{ addLabel }}
      </button>
    </div>
  </div>
</template>
