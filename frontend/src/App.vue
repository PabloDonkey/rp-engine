<script setup lang="ts"></script>

<template>
  <div class="min-h-screen">
    <header
      class="sticky top-0 z-10 flex items-center justify-between border-b border-black/10 bg-white/90 px-4 py-3 backdrop-blur dark:border-white/10 dark:bg-neutral-900/90"
    >
      <RouterLink to="/users" class="text-lg font-semibold tracking-tight">
        RP Engine Admin
      </RouterLink>
      <nav class="flex gap-4 text-sm font-medium text-neutral-600 dark:text-neutral-400">
        <RouterLink to="/users" class="hover:text-black dark:hover:text-white">Users</RouterLink>
        <RouterLink to="/scenarios" class="hover:text-black dark:hover:text-white"
          >Scenarios</RouterLink
        >
      </nav>
    </header>
    <main class="mx-auto max-w-5xl px-4 py-4">
      <RouterView />
    </main>
  </div>
</template>
