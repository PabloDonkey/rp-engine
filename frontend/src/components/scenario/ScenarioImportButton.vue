<script setup lang="ts">
import { ref } from "vue";

import { PButton } from "pablo-design-system";

/**
 * Imports one or more exported scenario files.
 *
 * `POST /admin/scenarios/import` has existed since S010 and nothing called it — importing
 * meant pasting JSON into the edit box. This closes that gap.
 *
 * One result line per file, and one file failing does not stop the rest. A batch import
 * that gives up halfway leaves you guessing which half landed.
 *
 * The import call arrives as a prop so this component can be tested without a store.
 */
const props = defineProps<{ importScenario: (payload: unknown) => Promise<{ id: string }> }>();

type Result = { file: string; ok: boolean; message: string };

const input = ref<HTMLInputElement | null>(null);
const results = ref<Result[]>([]);
const busy = ref(false);

async function onFiles(event: Event): Promise<void> {
  const picked = (event.target as HTMLInputElement).files;
  if (!picked?.length) return;

  results.value = [];
  busy.value = true;
  try {
    for (const file of Array.from(picked)) {
      results.value = [...results.value, await importOne(file)];
    }
  } finally {
    busy.value = false;
    // Cleared so picking the same file again still fires a change event.
    if (input.value) input.value.value = "";
  }
}

async function importOne(file: File): Promise<Result> {
  let payload: unknown;
  try {
    payload = JSON.parse(await file.text());
  } catch (error) {
    return {
      file: file.name,
      ok: false,
      message: `Invalid JSON: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
  try {
    const imported = await props.importScenario(payload);
    return { file: file.name, ok: true, message: `Imported as ${imported.id}` };
  } catch (error) {
    return {
      file: file.name,
      ok: false,
      message: error instanceof Error ? error.message : String(error),
    };
  }
}
</script>

<template>
  <div class="grid gap-1">
    <PButton as="label" :disabled="busy">
      {{ busy ? "Importing…" : "Import JSON" }}
      <input
        ref="input"
        type="file"
        accept="application/json,.json"
        multiple
        aria-label="Import JSON"
        class="hidden"
        :disabled="busy"
        @change="onFiles"
      />
    </PButton>
    <ul v-if="results.length" class="grid gap-0.5 text-micro">
      <li
        v-for="result in results"
        :key="result.file"
        :class="result.ok ? 'text-muted' : 'text-danger'"
      >
        <span class="font-mono">{{ result.file }}</span> — {{ result.message }}
      </li>
    </ul>
  </div>
</template>
