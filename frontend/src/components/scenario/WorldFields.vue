<script setup lang="ts">
import MetadataField from "@/components/form/MetadataField.vue";
import StringListField from "@/components/form/StringListField.vue";
import TextAreaField from "@/components/form/TextAreaField.vue";
import TextField from "@/components/form/TextField.vue";
import { emptyWorld } from "@/api/scenarioSchema";
import type { World } from "@/api/scenarioSchema";

/**
 * The world, behind a toggle.
 *
 * Off writes `null`, never an object of empty strings. An empty world object still renders
 * a world block into the prompt, which is a blank section the model has to read past.
 */
const world = defineModel<World | null>({ required: true });

function toggle(enabled: boolean): void {
  world.value = enabled ? emptyWorld() : null;
}
</script>

<template>
  <div class="grid gap-3">
    <label class="flex items-center gap-2">
      <input
        type="checkbox"
        :checked="world !== null"
        aria-label="This scenario has a world"
        @change="toggle(($event.target as HTMLInputElement).checked)"
      />
      <span>This scenario has a world</span>
    </label>
    <p v-if="world === null" class="text-xs text-neutral-500">
      No world. The prompt carries no world section.
    </p>

    <template v-else>
      <TextField
        v-model="world.id"
        label="World id"
        mono
        placeholder="old-city"
        hint="Internal. Players never see it."
      />
      <TextField v-model="world.name" label="World name" placeholder="The Old City" />
      <TextAreaField
        v-model="world.description"
        label="World description"
        :rows="4"
        placeholder="Damp stone, gas lamps, and a harbour that never sleeps."
      />
      <StringListField
        v-model="world.rules"
        label="World rules"
        hint="Facts about the world itself, separate from the scenario rules below."
        placeholder="Magic is rare and expensive."
        add-label="Add world rule"
      />
      <MetadataField v-model="world.metadata" label="World metadata" />
    </template>
  </div>
</template>
