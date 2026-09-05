<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";

import TagInput from "@/components/form/TagInput.vue";
import TextAreaField from "@/components/form/TextAreaField.vue";
import TextField from "@/components/form/TextField.vue";
import * as api from "@/api";
import type { LoreEntry, LoreEntryInput } from "@/api";

// An entry's id is a generated UUID (`AdminService.create_lorebook_entry`) — nothing in
// this panel shows or asks for one. Title is the identity a person works with, including
// for "related entries": pick from a list of titles, never type an id by hand.

/**
 * Memory layer 02 (ADR-026): the scenario's authored lore, retrieved by keyword trigger
 * during play rather than carried in every prompt. This section lists, creates, edits
 * and deletes entries directly against the admin API — it keeps its own state rather
 * than going through the shared admin store, since nothing else on the page needs it.
 */
const props = defineProps<{ scenarioId: string }>();

const entries = ref<LoreEntry[]>([]);
const loading = ref(false);
const listError = ref<string | null>(null);

// Not null (and isCreating false) while editing that entry's id; isCreating true for the
// create form; both false/null when the section is closed.
const editingId = ref<string | null>(null);
const isCreating = ref(false);
const draft = reactive<LoreEntryInput>(emptyDraft());
const saveBusy = ref(false);
const saveError = ref<string | null>(null);

function emptyDraft(): LoreEntryInput {
  return { title: "", content: "", triggerKeys: [], priority: "normal", relatedEntryIds: [] };
}

async function load(): Promise<void> {
  loading.value = true;
  listError.value = null;
  try {
    entries.value = await api.listLorebookEntries(props.scenarioId);
  } catch (error) {
    listError.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => props.scenarioId, load);

function startCreate(): void {
  isCreating.value = true;
  editingId.value = null;
  Object.assign(draft, emptyDraft());
  saveError.value = null;
}

function startEdit(entry: LoreEntry): void {
  isCreating.value = false;
  editingId.value = entry.id;
  Object.assign(draft, {
    title: entry.title,
    content: entry.content,
    triggerKeys: [...entry.trigger_keys],
    priority: entry.priority,
    relatedEntryIds: [...entry.related_entry_ids],
  });
  saveError.value = null;
}

function cancelEdit(): void {
  isCreating.value = false;
  editingId.value = null;
  saveError.value = null;
}

async function save(): Promise<void> {
  saveError.value = null;
  if (!draft.title.trim() || !draft.content.trim()) {
    saveError.value = "Title and content must not be empty.";
    return;
  }
  saveBusy.value = true;
  try {
    if (isCreating.value) {
      await api.createLoreEntry(props.scenarioId, draft);
    } else if (editingId.value) {
      await api.updateLoreEntry(props.scenarioId, editingId.value, draft);
    }
    cancelEdit();
    await load();
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : String(error);
  } finally {
    saveBusy.value = false;
  }
}

// Other entries this one can point to as "related" — never itself, named by title.
function relatableEntries(): LoreEntry[] {
  return entries.value.filter((entry) => entry.id !== editingId.value);
}

function toggleRelated(entryId: string): void {
  draft.relatedEntryIds = draft.relatedEntryIds.includes(entryId)
    ? draft.relatedEntryIds.filter((id) => id !== entryId)
    : [...draft.relatedEntryIds, entryId];
}

async function remove(entry: LoreEntry): Promise<void> {
  if (!window.confirm(`Delete lore entry "${entry.title}"? This cannot be undone.`)) return;
  listError.value = null;
  try {
    await api.deleteLoreEntry(props.scenarioId, entry.id);
    await load();
  } catch (error) {
    listError.value = error instanceof Error ? error.message : String(error);
  }
}
</script>

<template>
  <section>
    <div class="mb-2 flex items-center justify-between">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-500">Lorebook</h2>
      <button
        v-if="editingId === null && !isCreating"
        type="button"
        class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
        @click="startCreate"
      >
        New entry
      </button>
    </div>

    <p class="mb-2 text-xs text-neutral-500">
      Background facts retrieved during play when the conversation touches them — not carried
      in every prompt. See ADR-026 and <code>docs/MEMORY.md</code>.
    </p>

    <p v-if="loading" class="text-sm text-neutral-500">Loading…</p>
    <p v-else-if="listError" class="text-sm text-red-600 dark:text-red-400">{{ listError }}</p>
    <p v-else-if="entries.length === 0 && !isCreating" class="text-sm text-neutral-500">
      No lore entries yet.
    </p>

    <ul v-if="!loading && entries.length" class="grid gap-2">
      <li
        v-for="entry in entries"
        :key="entry.id"
        class="rounded-lg border border-black/10 p-3 dark:border-white/10"
      >
        <template v-if="editingId === entry.id">
          <div class="grid gap-3">
            <TextField v-model="draft.title" label="Title" />
            <TextAreaField v-model="draft.content" label="Content" :rows="4" />
            <div class="grid gap-1">
              <span class="text-xs text-neutral-500">Trigger keys</span>
              <TagInput v-model="draft.triggerKeys" label="Trigger keys" />
            </div>
            <fieldset v-if="relatableEntries().length" class="grid gap-1">
              <legend class="text-xs text-neutral-500">Related entries</legend>
              <label
                v-for="candidate in relatableEntries()"
                :key="candidate.id"
                class="flex items-center gap-2 text-sm"
              >
                <input
                  type="checkbox"
                  :checked="draft.relatedEntryIds.includes(candidate.id)"
                  @change="toggleRelated(candidate.id)"
                />
                {{ candidate.title }}
              </label>
            </fieldset>
            <p v-if="saveError" class="text-xs text-red-600 dark:text-red-400">{{ saveError }}</p>
            <div class="flex gap-2">
              <button
                type="button"
                class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
                :disabled="saveBusy"
                @click="save"
              >
                Save
              </button>
              <button
                type="button"
                class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
                :disabled="saveBusy"
                @click="cancelEdit"
              >
                Cancel
              </button>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ entry.title }}</span>
              </div>
              <p class="mt-1 text-sm">{{ entry.content }}</p>
              <div v-if="entry.trigger_keys.length" class="mt-1 flex flex-wrap gap-1">
                <span
                  v-for="key in entry.trigger_keys"
                  :key="key"
                  class="rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/10"
                >
                  {{ key }}
                </span>
              </div>
            </div>
            <div class="flex shrink-0 gap-2">
              <button
                type="button"
                class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
                @click="startEdit(entry)"
              >
                Edit
              </button>
              <button
                type="button"
                class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
                @click="remove(entry)"
              >
                Delete
              </button>
            </div>
          </div>
        </template>
      </li>
    </ul>

    <div
      v-if="isCreating"
      class="mt-2 grid gap-3 rounded-lg border border-black/10 p-3 dark:border-white/10"
    >
      <TextField v-model="draft.title" label="Title" />
      <TextAreaField v-model="draft.content" label="Content" :rows="4" />
      <div class="grid gap-1">
        <span class="text-xs text-neutral-500">Trigger keys</span>
        <TagInput v-model="draft.triggerKeys" label="Trigger keys" />
      </div>
      <fieldset v-if="relatableEntries().length" class="grid gap-1">
        <legend class="text-xs text-neutral-500">Related entries</legend>
        <label
          v-for="candidate in relatableEntries()"
          :key="candidate.id"
          class="flex items-center gap-2 text-sm"
        >
          <input
            type="checkbox"
            :checked="draft.relatedEntryIds.includes(candidate.id)"
            @change="toggleRelated(candidate.id)"
          />
          {{ candidate.title }}
        </label>
      </fieldset>
      <p v-if="saveError" class="text-xs text-red-600 dark:text-red-400">{{ saveError }}</p>
      <div class="flex gap-2">
        <button
          type="button"
          class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
          :disabled="saveBusy"
          @click="save"
        >
          Create
        </button>
        <button
          type="button"
          class="rounded-md border border-black/10 px-2 py-1 text-xs dark:border-white/10"
          :disabled="saveBusy"
          @click="cancelEdit"
        >
          Cancel
        </button>
      </div>
    </div>
  </section>
</template>
