<script setup lang="ts">
import { onMounted } from "vue";

import { PButton, PPanel } from "pablo-design-system";

import { useAdminStore } from "@/stores/admin";
import type { AdminUser } from "@/api";

const store = useAdminStore();

onMounted(() => {
  store.fetchUsers();
});

async function onToggleBlock(user: AdminUser): Promise<void> {
  const verb = user.is_blocked ? "Unblock" : "Block";
  if (!confirm(`${verb} ${user.display_name}?`)) return;
  await store.toggleBlock(user);
}
</script>

<template>
  <div>
    <h1 class="mb-3 text-xl font-semibold">Users</h1>

    <p v-if="store.usersLoading" class="text-body text-muted">Loading…</p>
    <p v-else-if="store.usersError" class="text-body text-danger">
      {{ store.usersError }}
    </p>
    <p v-else-if="store.users.length === 0" class="text-body text-muted">No users yet.</p>

    <ul class="flex flex-col gap-2">
      <li v-for="user in store.users" :key="user.id">
        <PPanel class="flex items-center justify-between gap-3 p-3">
          <RouterLink
            :to="{ name: 'user-sessions', params: { userId: user.id } }"
            class="min-w-0 flex-1"
          >
            <div class="truncate font-medium">{{ user.display_name }}</div>
            <div class="text-micro text-muted">
              {{ user.session_count }} session{{ user.session_count === 1 ? "" : "s" }}
              <span v-if="user.is_blocked" class="ml-2 text-danger">blocked</span>
            </div>
          </RouterLink>
          <PButton
            :variant="user.is_blocked ? 'secondary' : 'danger'"
            class="shrink-0"
            @click="onToggleBlock(user)"
          >
            {{ user.is_blocked ? "Unblock" : "Block" }}
          </PButton>
        </PPanel>
      </li>
    </ul>
  </div>
</template>
