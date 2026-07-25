<script setup lang="ts">
import { onMounted, watch } from "vue";

import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ userId: string }>();
const store = useAdminStore();

function load(): void {
  store.fetchUserSessions(props.userId);
}

onMounted(load);
watch(() => props.userId, load);

async function onDelete(sessionId: string): Promise<void> {
  if (!confirm("Delete this session? This clears its conversation too.")) return;
  await store.deleteSession(sessionId);
}
</script>

<template>
  <div>
    <RouterLink to="/users" class="text-sm text-neutral-500">&larr; Users</RouterLink>
    <h1 class="mb-3 mt-1 text-xl font-semibold">Sessions</h1>

    <p v-if="store.sessionsLoading" class="text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.sessionsError" class="text-sm text-red-600 dark:text-red-400">
      {{ store.sessionsError }}
    </p>
    <p v-else-if="store.sessions.length === 0" class="text-sm text-neutral-500">
      No sessions for this user.
    </p>

    <ul class="flex flex-col gap-2">
      <li
        v-for="session in store.sessions"
        :key="session.id"
        class="flex items-center justify-between gap-3 rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-neutral-900"
      >
        <RouterLink
          :to="{ name: 'session-detail', params: { sessionId: session.id } }"
          class="min-w-0 flex-1"
        >
          <div class="truncate font-medium">{{ session.scenario_definition_id }}</div>
          <div class="text-xs text-neutral-500">
            {{ new Date(session.created_at).toLocaleString() }}
          </div>
        </RouterLink>
        <button
          type="button"
          class="shrink-0 rounded-md border border-red-600 px-3 py-1.5 text-sm font-medium text-red-700 dark:text-red-400"
          @click="onDelete(session.id)"
        >
          Delete
        </button>
      </li>
    </ul>
  </div>
</template>
