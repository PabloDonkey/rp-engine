<script setup lang="ts">
import { ref, watch } from "vue";

import TagInput from "@/components/form/TagInput.vue";
import type { Metadata } from "@/api/scenarioSchema";

/**
 * Edits a metadata map, where a value is one string or a list of strings.
 *
 * The payload is an object, but the control holds an array of rows. An object cannot hold
 * a half-typed key, and it cannot keep two rows apart while someone renames one of them.
 * The rows are the edit model; the object is only what leaves on save.
 */
const props = defineProps<{ label: string; hint?: string }>();
const metadata = defineModel<Metadata>({ required: true });

type Row = { key: string; kind: "text" | "list"; text: string; list: string[] };

function toRows(value: Metadata): Row[] {
  return Object.entries(value).map(([key, item]) =>
    Array.isArray(item)
      ? { key, kind: "list", text: "", list: [...item] }
      : { key, kind: "text", text: item, list: [] },
  );
}

const rows = ref<Row[]>(toRows(metadata.value));

function toMetadata(source: Row[]): Metadata {
  const next: Metadata = {};
  for (const row of source) {
    const key = row.key.trim();
    // A row with no key is a row still being typed, not an entry. Skipping it is also what
    // makes a removed row leave nothing behind.
    if (!key) continue;
    next[key] = row.kind === "list" ? [...row.list] : row.text;
  }
  return next;
}

watch(
  metadata,
  (value) => {
    // Rebuild only when the new value did not come from these rows. Comparing beats a
    // "we are writing" flag, because the emit and this watcher do not run in the same tick:
    // a flag is already back to false by the time the watcher sees the echo, and the rebuild
    // would then delete the row the person is halfway through typing.
    if (JSON.stringify(value) === JSON.stringify(toMetadata(rows.value))) return;
    rows.value = toRows(value);
  },
  { deep: true },
);

watch(rows, () => (metadata.value = toMetadata(rows.value)), { deep: true });

function add(): void {
  rows.value = [...rows.value, { key: "", kind: "text", text: "", list: [] }];
}

function remove(index: number): void {
  rows.value = rows.value.filter((_, position) => position !== index);
}

/**
 * Switches one row between text and list.
 *
 * Text becomes a list by splitting on commas, because "noir, crime" in a text row is
 * almost always two values. A list becomes text by joining them back.
 */
function toggleKind(index: number): void {
  rows.value = rows.value.map((row, position) => {
    if (position !== index) return row;
    if (row.kind === "text") {
      const list = row.text
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);
      return { ...row, kind: "list", list, text: "" };
    }
    return { ...row, kind: "text", text: row.list.join(", "), list: [] };
  });
}
</script>

<template>
  <div class="grid gap-2">
    <span class="text-xs text-neutral-500">{{ props.label }}</span>
    <p v-if="hint" class="text-xs text-neutral-500">{{ hint }}</p>
    <p v-if="rows.length === 0" class="text-xs text-neutral-500">None yet.</p>

    <div
      v-for="(row, index) in rows"
      :key="index"
      class="grid gap-2 rounded-md border border-black/10 p-2 dark:border-white/10"
    >
      <div class="flex items-center gap-1">
        <input
          v-model="row.key"
          type="text"
          placeholder="key"
          :aria-label="`Metadata key ${index + 1}`"
          class="min-w-0 flex-1 rounded-md border border-black/10 bg-transparent px-2 py-1.5 font-mono dark:border-white/10"
        />
        <button
          type="button"
          :aria-label="`Switch ${row.key || `row ${index + 1}`} to ${row.kind === 'text' ? 'list' : 'text'}`"
          class="shrink-0 rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
          @click="toggleKind(index)"
        >
          {{ row.kind === "text" ? "text" : "list" }}
        </button>
        <button
          type="button"
          :aria-label="`Remove ${row.key || `row ${index + 1}`}`"
          class="shrink-0 rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
          @click="remove(index)"
        >
          &times;
        </button>
      </div>

      <TagInput
        v-if="row.kind === 'list'"
        v-model="row.list"
        :label="`Metadata values for ${row.key || `row ${index + 1}`}`"
      />
      <input
        v-else
        v-model="row.text"
        type="text"
        placeholder="value"
        :aria-label="`Metadata value ${index + 1}`"
        class="rounded-md border border-black/10 bg-transparent px-2 py-1.5 dark:border-white/10"
      />
    </div>

    <div>
      <button
        type="button"
        class="rounded-md border border-black/10 px-3 py-1 text-xs font-medium dark:border-white/10"
        @click="add"
      >
        Add metadata
      </button>
    </div>
  </div>
</template>
