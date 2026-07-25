<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ sessionId: string }>();
const store = useAdminStore();
const router = useRouter();
const showTraces = ref(false);

function load(): void {
  store.fetchSessionDetail(props.sessionId);
}

onMounted(load);
watch(() => props.sessionId, load);

const backTo = computed(() =>
  store.session ? { name: "user-sessions", params: { userId: store.session.owner_id } } : "/users",
);

async function onDelete(): Promise<void> {
  if (!confirm("Delete this session? This clears its conversation too.")) return;
  await store.deleteSession(props.sessionId);
  router.push(backTo.value);
}
</script>

<template>
  <div>
    <RouterLink :to="backTo" class="text-sm text-neutral-500">&larr; Sessions</RouterLink>

    <p v-if="store.sessionLoading" class="mt-2 text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.sessionError" class="mt-2 text-sm text-red-600 dark:text-red-400">
      {{ store.sessionError }}
    </p>

    <template v-else-if="store.session">
      <div class="mt-1 flex items-start justify-between gap-3">
        <h1 class="text-xl font-semibold">{{ store.session.scenario_definition_id }}</h1>
        <button
          type="button"
          class="shrink-0 rounded-md border border-red-600 px-3 py-1.5 text-sm font-medium text-red-700 dark:text-red-400"
          @click="onDelete"
        >
          Delete
        </button>
      </div>
      <div class="mb-4 text-xs text-neutral-500">
        {{ new Date(store.session.created_at).toLocaleString() }}
      </div>

      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Transcript
      </h2>
      <p v-if="store.transcript.length === 0" class="text-sm text-neutral-500">No messages yet.</p>
      <ol class="mb-6 flex flex-col gap-2">
        <li
          v-for="(message, index) in store.transcript"
          :key="index"
          class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10"
          :class="
            message.role === 'user'
              ? 'bg-blue-50 dark:bg-blue-950/40'
              : 'bg-white dark:bg-neutral-900'
          "
        >
          <div class="mb-1 text-xs font-semibold uppercase text-neutral-500">
            {{ message.role }}
          </div>
          <div class="whitespace-pre-wrap">{{ message.content }}</div>
        </li>
      </ol>

      <button
        type="button"
        class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500"
        @click="showTraces = !showTraces"
      >
        {{ showTraces ? "Hide" : "Show" }} generation traces ({{ store.traces.length }})
      </button>
      <ol v-if="showTraces" class="flex flex-col gap-2">
        <li
          v-for="(trace, index) in store.traces"
          :key="index"
          class="overflow-x-auto rounded-lg border border-black/10 bg-white p-3 text-xs dark:border-white/10 dark:bg-neutral-900"
        >
          <pre>{{ JSON.stringify(trace.record, null, 2) }}</pre>
        </li>
      </ol>
    </template>
  </div>
</template>
