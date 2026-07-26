<script setup lang="ts">
import { onMounted } from "vue";

import { useAdminStore } from "@/stores/admin";

const store = useAdminStore();

onMounted(() => {
  store.fetchScenarios();
});
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <h1 class="text-xl font-semibold">Scenarios</h1>
      <RouterLink
        :to="{ name: 'scenario-create' }"
        class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
      >
        New Scenario
      </RouterLink>
    </div>

    <p v-if="store.scenariosLoading" class="text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.scenariosError" class="text-sm text-red-600 dark:text-red-400">
      {{ store.scenariosError }}
    </p>
    <p v-else-if="store.scenarios.length === 0" class="text-sm text-neutral-500">
      No scenarios yet.
    </p>

    <ul class="flex flex-col gap-2">
      <li
        v-for="scenario in store.scenarios"
        :key="scenario.id"
        class="rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-neutral-900"
      >
        <RouterLink :to="{ name: 'scenario-detail', params: { scenarioId: scenario.id } }">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="truncate font-medium">{{ scenario.name }}</div>
              <div class="truncate text-xs text-neutral-500">{{ scenario.description }}</div>
            </div>
            <span
              v-if="scenario.visibility !== 'PUBLIC'"
              class="shrink-0 rounded-full border border-black/10 px-2 py-0.5 text-xs text-neutral-500 dark:border-white/10"
            >
              {{ scenario.visibility }}
            </span>
          </div>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
