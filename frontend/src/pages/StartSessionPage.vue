<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { PButton, PPanel } from "pablo-design-system";

import { useAdminStore } from "@/stores/admin";

/**
 * The panel's counterpart to `/play` plus Telegram's persona prompt (S036), folded into one
 * form: a scenario picker and the two persona fields at once, so none of Telegram's
 * `TelegramPendingPersonaStore` state machine comes along.
 */
const props = defineProps<{ userId: string }>();
const store = useAdminStore();
const router = useRouter();

const draft = reactive({ scenarioId: "", personaName: "", personaDescription: "" });
const submitting = ref(false);

onMounted(() => store.fetchScenarios(false));

async function onSubmit(): Promise<void> {
  if (!draft.scenarioId) return;
  submitting.value = true;
  try {
    const started = await store.startSession(
      props.userId,
      draft.scenarioId,
      draft.personaName.trim(),
      draft.personaDescription,
    );
    if (started) {
      router.push({ name: "session-detail", params: { sessionId: started.session.id } });
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'user-sessions', params: { userId } }" class="text-body text-muted">
      &larr; Sessions
    </RouterLink>
    <h1 class="mb-3 mt-1 text-xl font-semibold">Start a session</h1>

    <p v-if="store.scenariosLoading" class="text-body text-muted">Loading scenarios…</p>
    <p v-else-if="store.scenariosError" class="text-body text-danger">
      {{ store.scenariosError }}
    </p>

    <PPanel v-else class="p-3">
      <form class="grid gap-3" @submit.prevent="onSubmit">
        <label class="grid gap-1">
          <span class="text-micro text-muted">Scenario</span>
          <select
            v-model="draft.scenarioId"
            class="rounded-control border border-hairline bg-transparent px-2 py-1.5"
          >
            <option value="" disabled>Choose a scenario…</option>
            <option
              v-for="scenario in store.scenarios"
              :key="scenario.id"
              :value="scenario.id"
            >
              {{ scenario.name }}
            </option>
          </select>
          <span v-if="store.scenarios.length === 0" class="text-micro text-muted">
            No scenarios in the catalog yet.
          </span>
        </label>

        <div class="border-t border-hairline pt-3">
          <p class="mb-2 text-micro text-muted">
            Optional. Left blank, the session starts with no persona — the same as `/skip` on
            Telegram — and one can be set later from the session page. Ignored if this user
            already has a live session for the chosen scenario: that session is resumed
            instead, with the persona it already has.
          </p>
          <label class="grid gap-1">
            <span class="text-micro text-muted">Persona name</span>
            <input
              v-model="draft.personaName"
              type="text"
              maxlength="128"
              placeholder="Sera Vane"
              class="rounded-control border border-hairline bg-transparent px-2 py-1.5"
            />
          </label>
          <label class="mt-2 grid gap-1">
            <span class="text-micro text-muted">Persona description</span>
            <textarea
              v-model="draft.personaDescription"
              rows="3"
              placeholder="A wary courier who trusts machines more than people. Loves rain, hates crowds."
              class="rounded-control border border-hairline bg-transparent px-2 py-1.5"
            ></textarea>
          </label>
        </div>

        <p v-if="store.startSessionError" class="text-body text-danger">
          {{ store.startSessionError }}
        </p>

        <div>
          <PButton type="submit" :disabled="!draft.scenarioId || submitting">
            {{ submitting ? "Starting…" : "Start" }}
          </PButton>
        </div>
      </form>
    </PPanel>
  </div>
</template>
