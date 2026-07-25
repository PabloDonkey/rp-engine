<script setup lang="ts">
import { onMounted } from "vue";

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

    <p v-if="store.usersLoading" class="text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.usersError" class="text-sm text-red-600 dark:text-red-400">
      {{ store.usersError }}
    </p>
    <p v-else-if="store.users.length === 0" class="text-sm text-neutral-500">No users yet.</p>

    <ul class="flex flex-col gap-2">
      <li
        v-for="user in store.users"
        :key="user.id"
        class="flex items-center justify-between gap-3 rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-neutral-900"
      >
        <RouterLink
          :to="{ name: 'user-sessions', params: { userId: user.id } }"
          class="min-w-0 flex-1"
        >
          <div class="truncate font-medium">{{ user.display_name }}</div>
          <div class="text-xs text-neutral-500">
            {{ user.session_count }} session{{ user.session_count === 1 ? "" : "s" }}
            <span v-if="user.is_blocked" class="ml-2 text-red-600 dark:text-red-400"
              >blocked</span
            >
          </div>
        </RouterLink>
        <button
          type="button"
          class="shrink-0 rounded-md border px-3 py-1.5 text-sm font-medium"
          :class="
            user.is_blocked
              ? 'border-green-600 text-green-700 dark:text-green-400'
              : 'border-red-600 text-red-700 dark:text-red-400'
          "
          @click="onToggleBlock(user)"
        >
          {{ user.is_blocked ? "Unblock" : "Block" }}
        </button>
      </li>
    </ul>
  </div>
</template>
