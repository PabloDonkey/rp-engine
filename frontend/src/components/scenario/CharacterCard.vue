<script setup lang="ts">
import MetadataField from "@/components/form/MetadataField.vue";
import TextAreaField from "@/components/form/TextAreaField.vue";
import TextField from "@/components/form/TextField.vue";
import type { Character } from "@/api/scenarioSchema";

/**
 * One character, under its role key.
 *
 * The role is the map key in the payload, so two cards sharing a role would silently
 * become one. The parent checks that and passes the error down here.
 */
defineProps<{ index: number; roleError?: string | null }>();
defineEmits<{ remove: [] }>();

const role = defineModel<string>("role", { required: true });
const character = defineModel<Character>("character", { required: true });
</script>

<template>
  <div class="grid gap-3 rounded-lg border border-black/10 p-3 dark:border-white/10">
    <div class="flex items-start gap-2">
      <div class="min-w-0 flex-1">
        <TextField
          v-model="role"
          label="Role"
          mono
          placeholder="narrator"
          :error="roleError"
          hint="What the scenario calls this part. Must be unique."
        />
      </div>
      <button
        type="button"
        :aria-label="`Remove character ${index + 1}`"
        class="mt-5 shrink-0 rounded-md border border-black/10 px-2 py-1.5 text-xs dark:border-white/10"
        @click="$emit('remove')"
      >
        Remove
      </button>
    </div>

    <TextField v-model="character.id" label="Character id" mono placeholder="narrator" />
    <TextField v-model="character.name" label="Name" placeholder="The Narrator" />
    <TextAreaField
      v-model="character.description"
      label="Description"
      :rows="3"
      placeholder="A dry voice that has watched this city for a long time."
    />
    <TextAreaField
      v-model="character.personality"
      label="Personality"
      :rows="3"
      placeholder="Wry, patient, never raises its voice."
    />
    <TextAreaField
      v-model="character.greeting"
      label="Greeting"
      :rows="2"
      hint="Optional. The character's own opening line."
      :insertions="['{{user}}', '{{char}}', '{{world}}']"
    />
    <MetadataField v-model="character.metadata" label="Character metadata" />
  </div>
</template>
