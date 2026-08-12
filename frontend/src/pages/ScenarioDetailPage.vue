<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

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
    <RouterLink :to="{ name: 'scenarios' }" class="text-sm text-neutral-500"
      >&larr; Scenarios</RouterLink
    >

    <p v-if="store.scenarioLoading" class="mt-2 text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.scenarioError" class="mt-2 text-sm text-red-600 dark:text-red-400">
      {{ store.scenarioError }}
    </p>

    <template v-else-if="store.scenario">
      <div class="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h1 class="text-xl font-semibold">{{ store.scenario.name }}</h1>
          <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
            <code>{{ store.scenario.id }}</code>
            <span class="rounded border border-black/10 px-1.5 py-0.5 dark:border-white/10">
              {{ store.scenario.visibility }}
            </span>
            <span>
              {{ sessionCount }} live {{ sessionCount === 1 ? "session" : "sessions" }}
            </span>
          </div>
        </div>
        <div class="flex shrink-0 flex-wrap gap-2">
          <button
            v-if="isRetired"
            type="button"
            :disabled="lifecycleBusy"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium disabled:opacity-50 dark:border-white/10"
            @click="onRestore"
          >
            Restore
          </button>
          <button
            v-else
            type="button"
            :disabled="lifecycleBusy"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium disabled:opacity-50 dark:border-white/10"
            @click="onRetire"
          >
            Retire
          </button>
          <button
            type="button"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
            @click="onExport"
          >
            Export JSON
          </button>
          <RouterLink
            :to="{ name: 'scenario-edit', params: { scenarioId } }"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
          >
            Edit
          </RouterLink>
        </div>
      </div>

      <p
        v-if="isRetired"
        class="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm"
      >
        This scenario is retired. It is out of the catalog and <code>/play</code> refuses it.
        Stories already running it keep playing. Nothing was deleted.
      </p>
      <p v-if="lifecycleError" class="mt-3 text-sm text-red-600 dark:text-red-400">
        {{ lifecycleError }}
      </p>

      <div class="mt-5">
        <ScenarioReadView :scenario="store.scenario" />
      </div>

      <details class="mt-6">
        <summary class="cursor-pointer text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Raw JSON
        </summary>
        <pre
          class="mt-2 overflow-x-auto rounded-lg border border-black/10 bg-white p-3 text-xs dark:border-white/10 dark:bg-neutral-900"
          >{{ JSON.stringify(store.scenario, null, 2) }}</pre
        >
      </details>
    </template>
  </div>
</template>
