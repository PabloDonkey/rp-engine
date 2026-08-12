<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";

import ScenarioForm from "@/components/scenario/ScenarioForm.vue";
import { emptyScenario } from "@/api/scenarioSchema";
import type { ScenarioDefinition } from "@/api/scenarioSchema";
import { useAdminStore } from "@/stores/admin";

const LEAVE_WARNING = "This scenario has unsaved changes. Leave anyway?";

const props = defineProps<{ scenarioId?: string }>();
const store = useAdminStore();
const router = useRouter();

const isEdit = computed(() => !!props.scenarioId);
const form = ref<InstanceType<typeof ScenarioForm> | null>(null);
const initial = ref<ScenarioDefinition>(emptyScenario());
const dirty = ref(false);
const submitError = ref<string | null>(null);
const submitting = ref(false);

function load(): void {
  if (props.scenarioId) {
    store.fetchScenario(props.scenarioId);
  } else {
    initial.value = emptyScenario();
  }
}

onMounted(load);
watch(
  () => store.scenario,
  (scenario) => {
    if (isEdit.value && scenario) {
      initial.value = scenario;
    }
  },
);

// The browser's own guard, for a tab close or a reload. The router guard below covers
// moving inside the panel; neither can see the other's navigation.
function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value) return;
  event.preventDefault();
}

onMounted(() => window.addEventListener("beforeunload", onBeforeUnload));
onBeforeUnmount(() => window.removeEventListener("beforeunload", onBeforeUnload));

onBeforeRouteLeave(() => {
  if (!dirty.value) return true;
  return window.confirm(LEAVE_WARNING);
});

async function onSubmit(payload: ScenarioDefinition): Promise<void> {
  submitError.value = null;
  submitting.value = true;
  try {
    const saved = props.scenarioId
      ? await store.updateScenario(props.scenarioId, payload)
      : await store.createScenario(payload);
    // Cleared before the route change, or the leave guard stops the redirect that follows
    // a successful save.
    form.value?.markSaved();
    dirty.value = false;
    router.push({ name: "scenario-detail", params: { scenarioId: saved.id } });
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

    <h1 class="mb-4 mt-1 text-xl font-semibold">
      {{ isEdit ? "Edit Scenario" : "New Scenario" }}
    </h1>

    <p v-if="isEdit && store.scenarioLoading" class="text-sm text-neutral-500">Loading…</p>
    <p v-else-if="isEdit && store.scenarioError" class="text-sm text-red-600 dark:text-red-400">
      {{ store.scenarioError }}
    </p>
    <template v-else>
      <p v-if="submitError" class="mb-3 whitespace-pre-wrap text-sm text-red-600 dark:text-red-400">
        {{ submitError }}
      </p>
      <ScenarioForm
        ref="form"
        :initial="initial"
        :mode="isEdit ? 'edit' : 'create'"
        :busy="submitting"
        @submit="onSubmit"
        @dirty="dirty = $event"
      />
    </template>
  </div>
</template>
