<script setup lang="ts"></script>

<template>
  <div class="min-h-screen">
    <header
      class="sticky top-0 z-10 border-b border-black/10 bg-white/90 px-4 py-3 backdrop-blur dark:border-white/10 dark:bg-neutral-900/90"
    >
      <RouterLink to="/users" class="text-lg font-semibold tracking-tight">
        RP Engine Admin
      </RouterLink>
    </header>
    <main class="mx-auto max-w-3xl px-4 py-4">
      <RouterView />
    </main>
  </div>
</template>
