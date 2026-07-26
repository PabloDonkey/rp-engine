<script setup lang="ts">
import { onMounted, watch } from "vue";

import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ scenarioId: string }>();
const store = useAdminStore();

function load(): void {
  store.fetchScenario(props.scenarioId);
}

onMounted(load);
watch(() => props.scenarioId, load);

function onExport(): void {
  if (!store.scenario) return;
  const blob = new Blob([JSON.stringify(store.scenario, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${props.scenarioId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'scenarios' }" class="text-sm text-neutral-500"
      >&larr; Scenarios</RouterLink
    >

    <p v-if="store.scenarioLoading" class="mt-2 text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.scenarioError" class="mt-2 text-sm text-red-600 dark:text-red-400">
      {{ store.scenarioError }}
    </p>

    <template v-else-if="store.scenario">
      <div class="mt-1 flex items-start justify-between gap-3">
        <h1 class="text-xl font-semibold">{{ store.scenario.name }}</h1>
        <div class="flex shrink-0 gap-2">
          <button
            type="button"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
            @click="onExport"
          >
            Export
          </button>
          <RouterLink
            :to="{ name: 'scenario-edit', params: { scenarioId } }"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
          >
            Edit
          </RouterLink>
        </div>
      </div>
      <div class="mb-4 text-sm text-neutral-500">{{ store.scenario.description }}</div>

      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Definition
      </h2>
      <pre
        class="overflow-x-auto rounded-lg border border-black/10 bg-white p-3 text-xs dark:border-white/10 dark:bg-neutral-900"
        >{{ JSON.stringify(store.scenario, null, 2) }}</pre
      >
    </template>
  </div>
</template>
