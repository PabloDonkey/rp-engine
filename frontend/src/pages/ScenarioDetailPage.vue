<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { PButton, PChip, PSectionLabel } from "pablo-design-system";

import ScenarioReadView from "@/components/scenario/ScenarioReadView.vue";
import { retireMessage } from "@/components/scenario/retirePrompt";
import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ scenarioId: string }>();
const store = useAdminStore();

const lifecycleBusy = ref(false);
const lifecycleError = ref<string | null>(null);

// The list row, not the definition: `is_active` and the live session count are deliberately
// absent from the transfer payload. Absent means the scenario has no row yet, which is what
// a just-created scenario looks like for one render.
const summary = computed(() => store.scenarioSummary);
const isRetired = computed(() => summary.value?.is_active === false);
const sessionCount = computed(() => summary.value?.session_count ?? 0);

function load(): void {
  lifecycleError.value = null;
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

async function onRetire(): Promise<void> {
  if (!window.confirm(retireMessage(store.scenario?.name ?? "", sessionCount.value))) return;
  await runLifecycle(() => store.retireScenario(props.scenarioId));
}

async function onRestore(): Promise<void> {
  await runLifecycle(() => store.restoreScenario(props.scenarioId));
}

async function runLifecycle(action: () => Promise<void>): Promise<void> {
  lifecycleError.value = null;
  lifecycleBusy.value = true;
  try {
    await action();
  } catch (error) {
    lifecycleError.value = error instanceof Error ? error.message : String(error);
  } finally {
    lifecycleBusy.value = false;
  }
}
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'scenarios' }" class="text-body text-muted"
      >&larr; Scenarios</RouterLink
    >

    <p v-if="store.scenarioLoading" class="mt-2 text-body text-muted">Loading…</p>
    <p v-else-if="store.scenarioError" class="mt-2 text-body text-danger">
      {{ store.scenarioError }}
    </p>

    <template v-else-if="store.scenario">
      <div class="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h1 class="text-xl font-semibold">{{ store.scenario.name }}</h1>
          <div class="mt-1 flex flex-wrap items-center gap-2 text-micro text-muted">
            <code>{{ store.scenario.id }}</code>
            <PChip>{{ store.scenario.visibility }}</PChip>
            <span>
              {{ sessionCount }} live {{ sessionCount === 1 ? "session" : "sessions" }}
            </span>
          </div>
        </div>
        <div class="flex shrink-0 flex-wrap gap-2">
          <PButton v-if="isRetired" :disabled="lifecycleBusy" @click="onRestore">
            Restore
          </PButton>
          <PButton v-else :disabled="lifecycleBusy" @click="onRetire"> Retire </PButton>
          <PButton @click="onExport">Export JSON</PButton>
          <!-- RouterLink, not PButton: see ScenariosPage's "New Scenario" for why a
               design-system primitive doesn't route links. -->
          <RouterLink
            :to="{ name: 'scenario-edit', params: { scenarioId } }"
            class="inline-flex items-center justify-center gap-1.5 rounded-control border border-hairline bg-surface px-3 py-1.5 text-body font-medium text-ink transition-colors hover:bg-raised"
          >
            Edit
          </RouterLink>
        </div>
      </div>

      <p
        v-if="isRetired"
        class="mt-3 rounded-panel border border-warning bg-warning-soft p-3 text-body"
      >
        This scenario is retired. It is out of the catalog and <code>/play</code> refuses it.
        Stories already running it keep playing. Nothing was deleted.
      </p>
      <p v-if="lifecycleError" class="mt-3 text-body text-danger">
        {{ lifecycleError }}
      </p>

      <div class="mt-5">
        <ScenarioReadView :scenario="store.scenario" />
      </div>

      <details class="mt-6">
        <summary class="cursor-pointer">
          <PSectionLabel as="span" size="sm">Raw JSON</PSectionLabel>
        </summary>
        <pre
          class="mt-2 overflow-x-auto rounded-panel border border-hairline bg-surface p-3 text-xs"
          >{{ JSON.stringify(store.scenario, null, 2) }}</pre
        >
      </details>
    </template>
  </div>
</template>
