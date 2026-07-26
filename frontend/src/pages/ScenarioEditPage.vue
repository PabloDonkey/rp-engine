<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useAdminStore } from "@/stores/admin";

const NEW_SCENARIO_TEMPLATE = {
  id: "",
  owner_id: "00000000-0000-0000-0000-000000000000",
  name: "",
  description: "",
  world: null,
  characters: {},
  rules: [],
  story_graph: null,
  initial_context: "",
  visibility: "PUBLIC",
  allowed_group_chat_ids: [],
  metadata: {},
};

const props = defineProps<{ scenarioId?: string }>();
const store = useAdminStore();
const router = useRouter();

const isEdit = computed(() => !!props.scenarioId);
const text = ref(JSON.stringify(NEW_SCENARIO_TEMPLATE, null, 2));
const submitError = ref<string | null>(null);
const submitting = ref(false);

function load(): void {
  if (props.scenarioId) {
    store.fetchScenario(props.scenarioId);
  }
}

onMounted(load);
watch(
  () => store.scenario,
  (scenario) => {
    if (isEdit.value && scenario) {
      text.value = JSON.stringify(scenario, null, 2);
    }
  },
);

async function onSubmit(): Promise<void> {
  submitError.value = null;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(text.value);
  } catch (error) {
    submitError.value = `Invalid JSON: ${error instanceof Error ? error.message : String(error)}`;
    return;
  }

  submitting.value = true;
  try {
    const saved = props.scenarioId
      ? await store.updateScenario(props.scenarioId, payload)
      : await store.createScenario(payload);
    router.push({ name: "scenario-detail", params: { scenarioId: saved.id as string } });
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : String(error);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div>
    <RouterLink
      :to="isEdit ? { name: 'scenario-detail', params: { scenarioId } } : { name: 'scenarios' }"
      class="text-sm text-neutral-500"
    >
      &larr; {{ isEdit ? "Scenario" : "Scenarios" }}
    </RouterLink>

    <h1 class="mb-3 mt-1 text-xl font-semibold">
      {{ isEdit ? "Edit Scenario" : "New Scenario" }}
    </h1>

    <p v-if="store.scenarioLoading" class="text-sm text-neutral-500">Loading…</p>
    <template v-else>
      <p class="mb-2 text-xs text-neutral-500">
        Raw scenario JSON — see docs/SCENARIOS.md for the field reference. Saved through the same
        validation the curated catalog uses, so an invalid payload is rejected, not persisted.
      </p>
      <textarea
        v-model="text"
        rows="24"
        spellcheck="false"
        class="w-full rounded-lg border border-black/10 bg-white p-3 font-mono text-xs dark:border-white/10 dark:bg-neutral-900"
      />

      <p v-if="submitError" class="mt-2 text-sm text-red-600 dark:text-red-400">
        {{ submitError }}
      </p>

      <div class="mt-3 flex gap-2">
        <button
          type="button"
          class="rounded-md border border-black/10 bg-black px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:border-white/10 dark:bg-white dark:text-black"
          :disabled="submitting"
          @click="onSubmit"
        >
          {{ submitting ? "Saving…" : "Save" }}
        </button>
      </div>
    </template>
  </div>
</template>
