<script setup lang="ts">
import { PThemeToggle } from "pablo-design-system";
</script>

<template>
  <!-- `h-screen`, not `min-h-screen`: a minimum height is a floor, not a ceiling, so a
       page with more content than the viewport was free to grow this box (and the whole
       document) taller than 100vh -- which is the bug `main`'s own scrollbar below fixes
       properly. `overflow-hidden` backs that up: with a hard-capped height, nothing here
       should ever need its own scrollbar, but this keeps a header-height miscalculation
       from reopening the same bug instead of just growing `main`. -->
  <div class="flex h-screen flex-col overflow-hidden">
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
    <!-- `main` owns the scrollbar for every route now, instead of the document. Two
         reasons it has to be here and not on the outer `div`: the header must stay put
         (this is what makes `sticky` on it actually redundant, though harmless to keep),
         and a page that opts into filling this box exactly (`SessionDetailPage`, via its
         own `h-full flex flex-col`) needs `main`'s height to be real and fixed -- which
         only `h-screen` above plus `flex-1 min-h-0` here provides. `min-height: auto`
         (the flex-item default) would otherwise let `main` grow to fit whatever a page
         renders, taking the whole document with it, which is the bug this whole chain
         fixes: the composer ends up below the fold and the *document* scrolls instead of
         the page's own content. A page that doesn't opt into `h-full` (everything else)
         still renders at its natural content height, and `overflow-y-auto` here scrolls
         it in place if that height exceeds what's left under the header. -->
    <main class="mx-auto flex w-full max-w-5xl min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4">
      <RouterView />
    </main>
  </div>
</template>
