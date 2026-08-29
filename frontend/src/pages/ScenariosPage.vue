<script setup lang="ts">
import { onMounted, ref } from "vue";

import { PButton, PChip, PPanel } from "pablo-design-system";

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
        <!-- RouterLink, not PButton: a design-system primitive that needed vue-router to
             style a link would couple the package to one router, which the package is
             deliberately written not to assume. Hand-matched to PButton's secondary/md
             look instead. -->
        <RouterLink
          :to="{ name: 'scenario-create' }"
          class="inline-flex items-center justify-center gap-1.5 rounded-control border border-hairline bg-surface px-3 py-1.5 text-body font-medium text-ink transition-colors hover:bg-raised"
        >
          New Scenario
        </RouterLink>
      </div>
    </div>

    <label class="mb-3 flex items-center gap-2 text-body">
      <input
        type="checkbox"
        :checked="showRetired"
        @change="onToggleRetired(($event.target as HTMLInputElement).checked)"
      />
      <span>Show retired</span>
    </label>

    <p v-if="actionError" class="mb-2 text-body text-danger">
      {{ actionError }}
    </p>

    <p v-if="store.scenariosLoading" class="text-body text-muted">Loading…</p>
    <p v-else-if="store.scenariosError" class="text-body text-danger">
      {{ store.scenariosError }}
    </p>
    <p v-else-if="store.scenarios.length === 0" class="text-body text-muted">
      No scenarios yet.
    </p>

    <ul class="flex flex-col gap-2">
      <li v-for="scenario in store.scenarios" :key="scenario.id">
        <PPanel :class="['p-3', scenario.is_active ? '' : 'opacity-60']">
          <div class="flex items-center justify-between gap-2">
            <RouterLink
              :to="{ name: 'scenario-detail', params: { scenarioId: scenario.id } }"
              class="min-w-0 flex-1"
            >
              <div class="truncate font-medium">{{ scenario.name }}</div>
              <div class="truncate text-micro text-muted">{{ scenario.description }}</div>
              <div class="mt-0.5 text-micro text-muted">
                {{ scenario.session_count }} live
                {{ scenario.session_count === 1 ? "session" : "sessions" }}
              </div>
            </RouterLink>
            <div class="flex shrink-0 items-center gap-2">
              <PChip v-if="!scenario.is_active">retired</PChip>
              <PChip v-else-if="scenario.visibility !== 'PUBLIC'">
                {{ scenario.visibility }}
              </PChip>
              <PButton
                v-if="scenario.is_active"
                size="sm"
                :aria-label="`Retire ${scenario.name}`"
                :disabled="busyId === scenario.id"
                @click="onRetire(scenario)"
              >
                Retire
              </PButton>
              <PButton
                v-else
                size="sm"
                :aria-label="`Restore ${scenario.name}`"
                :disabled="busyId === scenario.id"
                @click="onRestore(scenario)"
              >
                Restore
              </PButton>
            </div>
          </div>
        </PPanel>
      </li>
    </ul>
  </div>
</template>
