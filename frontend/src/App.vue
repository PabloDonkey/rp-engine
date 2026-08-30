<script setup lang="ts">
import { PThemeToggle } from "pablo-design-system";
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header
      class="sticky top-0 z-10 flex shrink-0 items-center justify-between border-b border-black/10 bg-white/90 px-4 py-3 backdrop-blur dark:border-white/10 dark:bg-neutral-900/90"
    >
      <RouterLink to="/users" class="text-lg font-semibold tracking-tight">
        RP Engine Admin
      </RouterLink>
      <div class="flex items-center gap-4">
        <nav class="flex gap-4 text-sm font-medium text-neutral-600 dark:text-neutral-400">
          <RouterLink to="/users" class="hover:text-black dark:hover:text-white"
            >Users</RouterLink
          >
          <RouterLink to="/scenarios" class="hover:text-black dark:hover:text-white"
            >Scenarios</RouterLink
          >
        </nav>
        <PThemeToggle />
      </div>
    </header>
    <!-- `flex-1 flex-col` so a page that opts in (`SessionDetailPage`) can fill exactly
         the viewport height left under the header, rather than guessing it with a
         `calc()`. A page that doesn't opt in (everything else) renders at its own
         content height, same as before -- a flex item without its own `flex-1` just
         sizes to content. -->
    <main class="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 py-4">
      <RouterView />
    </main>
  </div>
</template>
