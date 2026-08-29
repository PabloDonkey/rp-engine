<script setup lang="ts">
import { onMounted, watch } from "vue";

import { PButton, PPanel } from "pablo-design-system";

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
    <RouterLink to="/users" class="text-body text-muted">&larr; Users</RouterLink>
    <h1 class="mb-3 mt-1 text-xl font-semibold">Sessions</h1>

    <p v-if="store.sessionsLoading" class="text-body text-muted">Loading…</p>
    <p v-else-if="store.sessionsError" class="text-body text-danger">
      {{ store.sessionsError }}
    </p>
    <p v-else-if="store.sessions.length === 0" class="text-body text-muted">
      No sessions for this user.
    </p>

    <ul class="flex flex-col gap-2">
      <li v-for="session in store.sessions" :key="session.id">
        <PPanel class="flex items-center justify-between gap-3 p-3">
          <RouterLink
            :to="{ name: 'session-detail', params: { sessionId: session.id } }"
            class="min-w-0 flex-1"
          >
            <div class="truncate font-medium">{{ session.scenario_definition_id }}</div>
            <div class="text-micro text-muted">
              {{ new Date(session.created_at).toLocaleString() }}
            </div>
          </RouterLink>
          <PButton variant="danger" class="shrink-0" @click="onDelete(session.id)">
            Delete
          </PButton>
        </PPanel>
      </li>
    </ul>
  </div>
</template>
