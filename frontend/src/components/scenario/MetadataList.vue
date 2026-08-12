<script setup lang="ts">
import type { Metadata } from "@/api/scenarioSchema";

/**
 * Renders a metadata map.
 *
 * A value is one string or a list of strings. A string prints as text; a list prints as
 * chips, so a `tags` array reads as tags rather than as a comma-soup line.
 */
defineProps<{ metadata: Metadata }>();
</script>

<template>
  <p v-if="Object.keys(metadata).length === 0" class="text-sm text-neutral-500">None.</p>
  <dl v-else class="grid gap-2 text-sm">
    <div v-for="(value, key) in metadata" :key="key" class="grid gap-1">
      <dt class="text-xs uppercase tracking-wide text-neutral-500">{{ key }}</dt>
      <dd v-if="Array.isArray(value)" class="flex flex-wrap gap-1">
        <span
          v-for="item in value"
          :key="item"
          class="rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/10"
        >
          {{ item }}
        </span>
        <span v-if="value.length === 0" class="text-xs text-neutral-500">Empty list.</span>
      </dd>
      <dd v-else class="whitespace-pre-wrap break-words">{{ value }}</dd>
    </div>
  </dl>
</template>
