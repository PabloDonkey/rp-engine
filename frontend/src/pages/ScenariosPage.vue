<script setup lang="ts">
import { onMounted, ref } from "vue";

import ScenarioImportButton from "@/components/scenario/ScenarioImportButton.vue";
import { retireMessage } from "@/components/scenario/retirePrompt";
import type { ScenarioSummary } from "@/api";
import { useAdminStore } from "@/stores/admin";

const store = useAdminStore();
const showRetired = ref(false);
const busyId = ref<string | null>(null);
const actionError = ref<string | null>(null);

onMounted(() => store.fetchScenarios(showRetired.value));

function onToggleRetired(value: boolean): void {
  showRetired.value = value;
  store.fetchScenarios(value);
}

async function onRetire(scenario: ScenarioSummary): Promise<void> {
  if (!window.confirm(retireMessage(scenario.name, scenario.session_count))) return;
  await run(scenario.id, () => store.retireScenario(scenario.id));
}

async function onRestore(scenario: ScenarioSummary): Promise<void> {
  await run(scenario.id, () => store.restoreScenario(scenario.id));
}

async function run(scenarioId: string, action: () => Promise<void>): Promise<void> {
  actionError.value = null;
  busyId.value = scenarioId;
  try {
    await action();
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : String(error);
  } finally {
    busyId.value = null;
  }
}
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-start justify-between gap-2">
      <h1 class="text-xl font-semibold">Scenarios</h1>
      <div class="flex flex-wrap items-start gap-2">
        <ScenarioImportButton :import-scenario="store.importScenario" />
        <RouterLink
          :to="{ name: 'scenario-create' }"
          class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
        >
          New Scenario
        </RouterLink>
      </div>
    </div>

    <label class="mb-3 flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        :checked="showRetired"
        @change="onToggleRetired(($event.target as HTMLInputElement).checked)"
      />
      <span>Show retired</span>
    </label>

    <p v-if="actionError" class="mb-2 text-sm text-red-600 dark:text-red-400">
      {{ actionError }}
    </p>

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
        :class="[
          'rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-neutral-900',
          scenario.is_active ? '' : 'opacity-60',
        ]"
      >
        <div class="flex items-center justify-between gap-2">
          <RouterLink
            :to="{ name: 'scenario-detail', params: { scenarioId: scenario.id } }"
            class="min-w-0 flex-1"
          >
            <div class="truncate font-medium">{{ scenario.name }}</div>
            <div class="truncate text-xs text-neutral-500">{{ scenario.description }}</div>
            <div class="mt-0.5 text-xs text-neutral-500">
              {{ scenario.session_count }} live
              {{ scenario.session_count === 1 ? "session" : "sessions" }}
            </div>
          </RouterLink>
          <div class="flex shrink-0 items-center gap-2">
            <span
              v-if="!scenario.is_active"
              class="rounded-full border border-black/10 px-2 py-0.5 text-xs text-neutral-500 dark:border-white/10"
            >
              retired
            </span>
            <span
              v-else-if="scenario.visibility !== 'PUBLIC'"
              class="rounded-full border border-black/10 px-2 py-0.5 text-xs text-neutral-500 dark:border-white/10"
            >
              {{ scenario.visibility }}
            </span>
            <button
              v-if="scenario.is_active"
              type="button"
              :aria-label="`Retire ${scenario.name}`"
              :disabled="busyId === scenario.id"
              class="rounded-md border border-black/10 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/10"
              @click="onRetire(scenario)"
            >
              Retire
            </button>
            <button
              v-else
              type="button"
              :aria-label="`Restore ${scenario.name}`"
              :disabled="busyId === scenario.id"
              class="rounded-md border border-black/10 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/10"
              @click="onRestore(scenario)"
            >
              Restore
            </button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>
