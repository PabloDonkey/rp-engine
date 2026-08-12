<script setup lang="ts">
import { computed, ref, watch } from "vue";

import CharacterCard from "@/components/scenario/CharacterCard.vue";
import FormSection from "@/components/form/FormSection.vue";
import MetadataField from "@/components/form/MetadataField.vue";
import OptionCards from "@/components/form/OptionCards.vue";
import StringListField from "@/components/form/StringListField.vue";
import TagInput from "@/components/form/TagInput.vue";
import TextAreaField from "@/components/form/TextAreaField.vue";
import TextField from "@/components/form/TextField.vue";
import WorldFields from "@/components/scenario/WorldFields.vue";
import {
  ScenarioDefinitionSchema,
  ScenarioIdSchema,
  SYSTEM_OWNER_ID,
  duplicateRoleKeys,
  emptyCharacter,
  emptyScenario,
} from "@/api/scenarioSchema";
import type { Character, ScenarioDefinition, StoryGraph } from "@/api/scenarioSchema";

/**
 * The whole scenario, as a form.
 *
 * **It carries every field, on screen or not.** The form builds the entire payload on save,
 * so a field with no control is a field the save wipes. `owner_id` is the one field with no
 * control on purpose: the panel always writes the system owner, so it is set on save rather
 * than shown.
 *
 * Section order matches the read view, which matches the order `ConversationBuilder`
 * assembles the prompt.
 */
const props = defineProps<{ initial: ScenarioDefinition; mode: "create" | "edit"; busy?: boolean }>();
const emit = defineEmits<{ submit: [payload: ScenarioDefinition]; dirty: [value: boolean] }>();

const VISIBILITY_OPTIONS = [
  {
    value: "PUBLIC",
    label: "Public",
    description: "Listed in /scenarios and playable by anyone.",
  },
  {
    value: "UNLISTED",
    label: "Unlisted",
    description: "Hidden from /scenarios, but playable by anyone who knows the id.",
  },
  {
    value: "RESTRICTED",
    label: "Restricted",
    description: "Listed and playable only in the group chats you name.",
  },
] as const;

const PLACEHOLDERS = ["{{user}}", "{{char}}", "{{world}}"] as const;

type CharacterRow = { role: string; character: Character };

/**
 * A deep copy, so editing the draft never writes back into the loaded scenario.
 *
 * A JSON round trip rather than the built-in structured clone: the value arriving as a prop
 * may be a Vue reactive proxy, which the built-in refuses. The payload is plain JSON data by
 * definition, so nothing is lost.
 */
function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const draft = ref<ScenarioDefinition>(clone(props.initial));
const characterRows = ref<CharacterRow[]>(toRows(props.initial.characters));
// The story graph is inert data no scenario uses, so it stays raw JSON under Advanced
// rather than earning a beat editor.
const storyGraphText = ref(serializeGraph(props.initial.story_graph));
const storyGraphError = ref<string | null>(null);
const submitError = ref<string | null>(null);
// What the form looked like when it loaded, so the leave guard compares against the saved
// state rather than against a blank.
const pristine = ref(snapshot());

function toRows(characters: Record<string, Character>): CharacterRow[] {
  return Object.entries(characters).map(([role, character]) => ({
    role,
    character: clone(character),
  }));
}

function serializeGraph(graph: StoryGraph | null): string {
  return graph === null ? "" : JSON.stringify(graph, null, 2);
}

function snapshot(): string {
  return JSON.stringify([draft.value, characterRows.value, storyGraphText.value]);
}

watch(
  () => props.initial,
  (value) => {
    draft.value = clone(value);
    characterRows.value = toRows(value.characters);
    storyGraphText.value = serializeGraph(value.story_graph);
    pristine.value = snapshot();
  },
);

const isDirty = computed(() => snapshot() !== pristine.value);
watch(isDirty, (value) => emit("dirty", value), { immediate: true });

const repeatedRoles = computed(() =>
  duplicateRoleKeys(characterRows.value.map((row) => row.role.trim()).filter(Boolean)),
);

const idError = computed(() => {
  // Only when creating: an existing id is locked, and judging a stored id by today's rule
  // would show an error on a field nobody can fix.
  if (props.mode === "edit") return null;
  if (draft.value.id === "") return null;
  const result = ScenarioIdSchema.safeParse(draft.value.id);
  return result.success ? null : (result.error.issues[0]?.message ?? "Invalid id");
});

function roleError(role: string): string | null {
  const trimmed = role.trim();
  if (!trimmed) return "Role is required";
  return repeatedRoles.value.includes(trimmed) ? "Two characters share this role" : null;
}

function addCharacter(): void {
  characterRows.value = [...characterRows.value, { role: "", character: emptyCharacter() }];
}

function removeCharacter(index: number): void {
  characterRows.value = characterRows.value.filter((_, position) => position !== index);
}

function resetToBlank(): void {
  draft.value = emptyScenario();
  characterRows.value = [];
  storyGraphText.value = "";
}

/** Builds the payload, or returns null and sets the error that stopped it. */
function build(): ScenarioDefinition | null {
  storyGraphError.value = null;
  submitError.value = null;

  let storyGraph: StoryGraph | null = null;
  const graphText = storyGraphText.value.trim();
  if (graphText) {
    try {
      storyGraph = JSON.parse(graphText) as StoryGraph;
    } catch (error) {
      storyGraphError.value = `Invalid JSON: ${error instanceof Error ? error.message : String(error)}`;
      return null;
    }
  }

  if (repeatedRoles.value.length) {
    submitError.value = `Two characters share a role: ${repeatedRoles.value.join(", ")}`;
    return null;
  }

  const characters: Record<string, Character> = {};
  for (const row of characterRows.value) {
    const role = row.role.trim();
    if (!role) {
      submitError.value = "Every character needs a role";
      return null;
    }
    characters[role] = row.character;
  }

  const candidate = {
    ...draft.value,
    // Never shown, always the system owner. The panel does not author personal scenarios.
    owner_id: SYSTEM_OWNER_ID,
    characters,
    story_graph: storyGraph,
    // Only read when the visibility is RESTRICTED, so anything left over from an earlier
    // choice is dropped rather than carried invisibly.
    allowed_group_chat_ids:
      draft.value.visibility === "RESTRICTED" ? draft.value.allowed_group_chat_ids : [],
  };

  if (props.mode === "create") {
    const id = ScenarioIdSchema.safeParse(candidate.id);
    if (!id.success) {
      submitError.value = id.error.issues[0]?.message ?? "Invalid id";
      return null;
    }
  }

  const checked = ScenarioDefinitionSchema.safeParse(candidate);
  if (!checked.success) {
    submitError.value = checked.error.issues
      .map((issue) => `${issue.path.join(".") || "payload"}: ${issue.message}`)
      .join("\n");
    return null;
  }
  return checked.data;
}

function onSubmit(): void {
  const payload = build();
  if (payload) emit("submit", payload);
}

/** Called by the page once a save lands, so the leave guard stops warning. */
function markSaved(): void {
  pristine.value = snapshot();
}

defineExpose({ markSaved, resetToBlank });
</script>

<template>
  <form class="grid gap-6" @submit.prevent="onSubmit">
    <FormSection
      title="Overview"
      hint="The description is the first thing the prompt carries."
    >
      <TextField
        v-model="draft.id"
        label="Id"
        mono
        :locked="mode === 'edit'"
        :error="idError"
        placeholder="sealed-vault"
        :hint="
          mode === 'edit'
            ? 'Locked. Changing an id would orphan every story already running it.'
            : 'Players type this after /play, so keep it short.'
        "
      />
      <TextField v-model="draft.name" label="Name" placeholder="The Sealed Vault" />
      <TextAreaField
        v-model="draft.description"
        label="Description"
        :rows="3"
        placeholder="A tense heist beneath the old city."
      />
    </FormSection>

    <FormSection
      title="Opening scene"
      hint="The first thing the player reads. The placeholders below are replaced when the prompt is built."
    >
      <TextAreaField
        v-model="draft.initial_context"
        label="Opening scene"
        :rows="6"
        :insertions="PLACEHOLDERS"
        placeholder="You crouch by the vault door. The lamp gutters."
      />
    </FormSection>

    <FormSection title="World">
      <WorldFields v-model="draft.world" />
    </FormSection>

    <FormSection
      title="Characters"
      hint="Keyed by role. No characters at all is valid, and means a freeform scenario."
    >
      <p v-if="characterRows.length === 0" class="text-xs text-neutral-500">
        No characters. This is a freeform scenario.
      </p>
      <CharacterCard
        v-for="(row, index) in characterRows"
        :key="index"
        v-model:role="row.role"
        v-model:character="row.character"
        :index="index"
        :role-error="roleError(row.role)"
        @remove="removeCharacter(index)"
      />
      <div>
        <button
          type="button"
          class="rounded-md border border-black/10 px-3 py-1 text-xs font-medium dark:border-white/10"
          @click="addCharacter"
        >
          Add character
        </button>
      </div>
    </FormSection>

    <FormSection title="Rules" hint="The prompt lists these in this order, so the order matters.">
      <StringListField
        v-model="draft.rules"
        label="Scenario rules"
        placeholder="Stay in character at all times."
        add-label="Add rule"
      />
    </FormSection>

    <FormSection title="Access">
      <OptionCards
        v-model="draft.visibility"
        label="Who can see and play this"
        name="visibility"
        :options="VISIBILITY_OPTIONS"
      />
      <div v-if="draft.visibility === 'RESTRICTED'" class="grid gap-1">
        <span class="text-xs text-neutral-500">Allowed group chat ids</span>
        <TagInput v-model="draft.allowed_group_chat_ids" label="Allowed group chat ids" />
        <p class="text-xs text-neutral-500">
          Leave this empty and nobody can play it. Switching away from Restricted clears the
          list.
        </p>
      </div>
    </FormSection>

    <FormSection title="Metadata" hint="Never reaches the prompt. For your own notes.">
      <MetadataField v-model="draft.metadata" label="Scenario metadata" />
    </FormSection>

    <details>
      <summary class="cursor-pointer text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Advanced
      </summary>
      <div class="mt-2 grid gap-2 rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <p class="text-xs text-neutral-500">
          The story graph is inert data. Nothing in the engine walks these beats yet, and no
          scenario uses it, so it stays raw JSON. Leave it empty for no graph.
        </p>
        <textarea
          v-model="storyGraphText"
          rows="8"
          aria-label="Story graph JSON"
          spellcheck="false"
          :class="[
            'rounded-md border bg-transparent px-2 py-1.5 font-mono text-xs',
            storyGraphError ? 'border-red-500' : 'border-black/10 dark:border-white/10',
          ]"
        ></textarea>
        <p v-if="storyGraphError" class="text-xs text-red-600 dark:text-red-400">
          {{ storyGraphError }}
        </p>
      </div>
    </details>

    <p v-if="submitError" class="whitespace-pre-wrap text-sm text-red-600 dark:text-red-400">
      {{ submitError }}
    </p>

    <div class="flex items-center gap-2">
      <button
        type="submit"
        :disabled="busy"
        class="rounded-md border border-black/10 px-4 py-1.5 text-sm font-medium disabled:opacity-50 dark:border-white/10"
      >
        {{ busy ? "Saving…" : "Save" }}
      </button>
      <span v-if="isDirty" class="text-xs text-neutral-500">Unsaved changes</span>
    </div>
  </form>
</template>
