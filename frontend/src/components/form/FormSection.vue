<script setup lang="ts">
/** One titled card in a form. The title matches the read view, so the two pages line up. */
defineProps<{ title: string; hint?: string }>();
</script>

<template>
  <section>
    <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
      {{ title }}
    </h2>
    <div class="grid gap-3 rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
      <p v-if="hint" class="text-xs text-neutral-500">{{ hint }}</p>
      <slot />
    </div>
  </section>
</template>
