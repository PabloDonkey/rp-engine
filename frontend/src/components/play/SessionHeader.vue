<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { PButton, PChip, PPanel, PSectionLabel, PTabs } from "pablo-design-system";

import { useAdminStore } from "@/stores/admin";

/**
 * Title, meta, Export/Delete, and the Persona/Memory/Directives drawer.
 *
 * Everything here reads the admin store directly rather than taking props for session
 * data -- the store is a page-wide singleton, and prop-drilling its fields through would
 * just be a second name for the same value. `sessionId` is the one thing genuinely local
 * to "which session is this": every store action below needs it explicitly.
 */
const props = defineProps<{ sessionId: string }>();
const store = useAdminStore();

const emit = defineEmits<{
  export: [];
  delete: [];
}>();

// Memory layers (ADR-026). Only the toggleable ones are listed: the recent conversation is
// the story itself, so there is no state to show for it.
const MEMORY_LAYERS: { id: string; label: string; hint: string }[] = [
  {
    id: "rolling_summary",
    label: "Rolling summary",
    hint: "Condenses what falls out of the recent window into a running recap.",
  },
];
function memoryEnabled(sourceId: string): boolean {
  return store.sessionMemory?.settings.enabled_sources.includes(sourceId) ?? false;
}

function onToggleMemory(sourceId: string): Promise<boolean> {
  return store.setSessionMemorySource(props.sessionId, sourceId, !memoryEnabled(sourceId));
}

function onRunSummary(): Promise<boolean> {
  return store.refreshSessionSummary(props.sessionId);
}

// What the last pass did, in a sentence. A pass that wrote nothing must not read like one
// that worked, which is the whole reason the outcome is reported at all.
const PASS_REPORT: Record<string, string> = {
  folded: "Recap updated with the turns that were waiting.",
  condensed: "The recap had outgrown its share, so it was shortened.",
  waiting_for_batch: "Nothing done — too few turns are waiting to be worth a model call.",
  up_to_date: "Nothing to do — the recap already covers everything past the fold line.",
  model_wrote_nothing:
    "The model returned no recap, so nothing changed. It spent its budget thinking. " +
    "Press again, or raise RP_ENGINE_MEMORY_SUMMARY_MAX_TOKENS.",
  nothing_to_do: "Nothing to do — this session has no story yet.",
};

const passReport = computed(() => {
  const outcome = store.sessionMemory?.last_pass;
  if (!outcome) return "";
  return PASS_REPORT[outcome] ?? outcome;
});

const passFailed = computed(() => store.sessionMemory?.last_pass === "model_wrote_nothing");

const memoryStatus = computed(() => store.sessionMemory?.status ?? null);

// The story, oldest first, as three shares of its turns: in the recap, waiting to be
// folded, and still replayed word for word. They always add up to the whole story.
const storyMap = computed(() => {
  const status = memoryStatus.value;
  if (!status || status.turns_total === 0) return null;
  const share = (turns: number) => (turns / status.turns_total) * 100;
  return {
    covered: { turns: status.covers_through_turn, percent: share(status.covers_through_turn) },
    pending: { turns: status.pending_turns, percent: share(status.pending_turns) },
    verbatim: { turns: status.verbatim_turns, percent: share(status.verbatim_turns) },
  };
});

// How full the next batch is. This fills and empties: folding a turn into the recap does
// not delete it, so the window itself never shrinks.
const foldPercent = computed(() =>
  memoryStatus.value ? Math.round(memoryStatus.value.fold_progress * 100) : 0,
);

// The recap against its own share of the budget. Over 100% means the pass will condense it.
const recapPercent = computed(() => {
  const status = memoryStatus.value;
  if (!status || status.summary_budget_tokens <= 0) return 0;
  return Math.round((status.summary_tokens / status.summary_budget_tokens) * 100);
});

const foldState = computed(() => {
  const status = memoryStatus.value;
  if (!status) return "";
  if (status.behind_turns > 0) {
    return `${status.behind_turns} turn(s) left the window uncovered — the next pass folds them at once`;
  }
  if (status.pending_turns === 0) {
    return "Nothing waiting. The recap covers everything past the fold line.";
  }
  if (status.fold_progress >= 1) {
    return `${status.pending_turns} turn(s) waiting — the next pass folds them`;
  }
  return `${status.pending_turns} turn(s) waiting, still under the batch the pass waits for`;
});

// The operator exception to the set-once contract (ADR-025): a player can only change a
// persona with /clear, an admin can correct one in place. Superseded sessions are excluded
// because a persona there would never reach a prompt.
const personaDraft = reactive({ name: "", description: "" });
const personaSaving = ref(false);

const canEditPersona = computed(() => store.session !== null && !store.session.deleted_at);
const hasPersona = computed(() => Boolean(store.session?.user_persona_name));

// Keep the draft in step with whichever session is loaded, so the form opens on what is
// currently stored rather than on a stale edit.
watch(
  () => store.session,
  (session) => {
    personaDraft.name = session?.user_persona_name ?? "";
    personaDraft.description = session?.user_persona_description ?? "";
  },
  { immediate: true },
);

const personaDirty = computed(
  () =>
    personaDraft.name !== (store.session?.user_persona_name ?? "") ||
    personaDraft.description !== (store.session?.user_persona_description ?? ""),
);

async function onSavePersona(): Promise<void> {
  if (!personaDraft.name.trim()) return;
  // Renaming re-renders past turns under the new name — transcripts store `{{user}}`
  // unresolved — so the story stops matching what the player actually read.
  if (
    hasPersona.value &&
    personaDraft.name.trim() !== store.session?.user_persona_name &&
    !confirm(
      `Rename this player's character from "${store.session?.user_persona_name}" to ` +
        `"${personaDraft.name.trim()}"? Past turns will render under the new name, which ` +
        "will not match what the player already read.",
    )
  ) {
    return;
  }
  personaSaving.value = true;
  try {
    await store.setSessionPersona(props.sessionId, personaDraft.name, personaDraft.description);
  } finally {
    personaSaving.value = false;
  }
}

// What each closed panel says about itself.
type PanelId = "persona" | "memory" | "directives";

/** One panel open at a time. They are reference, not things to read side by side. */
const openPanel = ref<PanelId | null>(null);

/** PTabs emits a plain string (it doesn't know about PanelId) — the cast is safe because
 *  the ids it can emit are exactly the ones PANELS below hands it. */
function togglePanel(id: string): void {
  openPanel.value = openPanel.value === id ? null : (id as PanelId);
}

const PANELS = computed<{ id: PanelId; label: string; summary: string }[]>(() => [
  { id: "persona", label: "Persona", summary: personaSummary.value },
  { id: "memory", label: "Memory", summary: memorySummary.value },
  { id: "directives", label: "Directives", summary: directivesSummary.value },
]);

const personaSummary = computed(() => store.session?.user_persona_name ?? "not set");

const memorySummary = computed(() => {
  const status = memoryStatus.value;
  if (!status || status.budget_tokens === 0) return "";
  return `${Math.round((status.window_tokens / status.budget_tokens) * 100)}% of the window`;
});

const directivesSummary = computed(() => {
  const directives = store.session?.directives;
  if (!directives) return "";
  const parts = [directives.language];
  if (directives.rules.length > 0) parts.push(`${directives.rules.length} rule(s)`);
  if (directives.director_instructions.length > 0) {
    parts.push(`${directives.director_instructions.length} note(s)`);
  }
  return parts.join(" · ");
});
</script>

<template>
  <div v-if="store.session">
    <div class="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h1 class="text-title font-semibold text-ink">
          {{ store.session.scenario_definition_id }}
        </h1>
        <span class="text-micro text-muted">
          {{ new Date(store.session.created_at).toLocaleString() }}
        </span>
        <PChip
          v-if="store.session.deleted_at"
          :title="`Superseded ${new Date(store.session.deleted_at).toLocaleString()}`"
        >
          superseded
        </PChip>
      </div>
      <div class="flex shrink-0 gap-2">
        <PButton size="sm" @click="emit('export')">Export</PButton>
        <PButton size="sm" variant="danger" @click="emit('delete')">Delete</PButton>
      </div>
    </div>

    <!-- One compact row, one open panel. Three stacked full-width cards cost the story
         about 180px of height before it started, and only one of them is ever read at a
         time. -->
    <div class="mb-3 mt-2">
      <PTabs :tabs="PANELS" :model-value="openPanel" @update:model-value="togglePanel" />

      <!-- `v-show` inside, not `v-if`: the persona draft is edit state and must survive
           opening a different panel. -->
      <PPanel v-if="openPanel" class="mt-2 max-h-[50vh] overflow-y-auto p-3">
        <div v-show="openPanel === 'persona'">
          <!-- Editable here, but only here: /clear is still the only way a *player* can
               change their character. An admin sees the whole session, so they can correct
               one. -->
          <form v-if="canEditPersona" class="grid gap-2" @submit.prevent="onSavePersona">
            <p v-if="!hasPersona" class="text-micro text-muted">
              <!-- v-pre: the placeholder is literal text, not an interpolation. -->
              This session has no persona, so <code v-pre>{{user}}</code> falls back to the
              player's Telegram name.
            </p>
            <p v-else class="text-micro text-muted">
              The player cannot change this themselves — /clear starts a fresh session
              instead. Renaming re-renders past turns under the new name.
            </p>
            <label class="grid gap-1">
              <span class="text-micro text-muted">Name</span>
              <input
                v-model="personaDraft.name"
                type="text"
                maxlength="128"
                placeholder="Sera Vane"
                class="rounded-control border border-hairline bg-transparent px-2 py-1.5"
              />
            </label>
            <label class="grid gap-1">
              <span class="text-micro text-muted">Description</span>
              <textarea
                v-model="personaDraft.description"
                rows="3"
                placeholder="A wary courier who trusts machines more than people. Loves rain, hates crowds."
                class="rounded-control border border-hairline bg-transparent px-2 py-1.5"
              ></textarea>
            </label>
            <div>
              <PButton
                type="submit"
                :disabled="!personaDraft.name.trim() || !personaDirty || personaSaving"
              >
                {{ personaSaving ? "Saving…" : hasPersona ? "Update persona" : "Set persona" }}
              </PButton>
            </div>
          </form>

          <!-- Superseded: read-only. Nothing here would ever reach a prompt again. -->
          <dl v-else-if="hasPersona" class="grid gap-2">
            <div class="flex gap-2">
              <dt class="w-32 shrink-0 text-muted">Name</dt>
              <dd>{{ store.session.user_persona_name }}</dd>
            </div>
            <div class="flex gap-2">
              <dt class="w-32 shrink-0 text-muted">Description</dt>
              <dd>
                <span v-if="!store.session.user_persona_description" class="text-muted">
                  None
                </span>
                <span v-else class="whitespace-pre-wrap">
                  {{ store.session.user_persona_description }}
                </span>
              </dd>
            </div>
            <p class="text-micro text-muted">
              This session was superseded, so its persona is read-only.
            </p>
          </dl>

          <p v-else class="text-body text-muted">
            No persona, and this session was superseded — a persona set here would never
            reach a prompt.
          </p>
        </div>
        <div v-show="openPanel === 'memory'" class="grid gap-3">
          <!-- The same switch the player has through /memory. -->
          <div v-for="layer in MEMORY_LAYERS" :key="layer.id" class="flex items-start gap-3">
            <PButton size="sm" :disabled="store.memoryBusy" @click="onToggleMemory(layer.id)">
              {{ memoryEnabled(layer.id) ? "On" : "Off" }}
            </PButton>
            <div>
              <div>{{ layer.label }}</div>
              <div class="text-micro text-muted">{{ layer.hint }}</div>
            </div>
          </div>

          <!-- The story, split the way memory splits it. The numbers are the ones the
               background worker itself uses. -->
          <div v-if="memoryStatus" class="grid gap-3 border-t border-hairline pt-3">
            <div v-if="storyMap" class="grid gap-1">
              <div class="flex flex-wrap items-baseline justify-between gap-2">
                <PSectionLabel as="span" size="sm">The story, oldest first</PSectionLabel>
                <span class="font-mono text-micro tabular-nums">
                  {{ memoryStatus.turns_total }} turns
                </span>
              </div>
              <!-- Categorical, not semantic: three fixed colours distinguish recap /
                   pending / verbatim, none of which is "the accent" or "a warning". No
                   token in the package models that, so these three stay literal on
                   purpose (S032 audit). -->
              <div class="flex h-3 overflow-hidden rounded-full bg-hairline-soft">
                <div
                  class="h-full bg-teal-600"
                  :style="{ width: `${storyMap.covered.percent}%` }"
                  :title="`${storyMap.covered.turns} turn(s) in the recap`"
                ></div>
                <div
                  class="h-full bg-amber-500"
                  :style="{ width: `${storyMap.pending.percent}%` }"
                  :title="`${storyMap.pending.turns} turn(s) waiting to be folded`"
                ></div>
                <div
                  class="h-full bg-sky-600"
                  :style="{ width: `${storyMap.verbatim.percent}%` }"
                  :title="`${storyMap.verbatim.turns} turn(s) replayed word for word`"
                ></div>
              </div>
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-micro text-muted">
                <span class="flex items-center gap-1.5">
                  <span class="h-2 w-2 rounded-full bg-teal-600"></span>
                  {{ storyMap.covered.turns }} in the recap
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="h-2 w-2 rounded-full bg-amber-500"></span>
                  {{ storyMap.pending.turns }} waiting to fold
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="h-2 w-2 rounded-full bg-sky-600"></span>
                  {{ storyMap.verbatim.turns }} word for word
                </span>
              </div>
              <div class="text-micro text-muted">
                <template v-if="memoryStatus.whole_story_fits">
                  Every stored turn still reaches the prompt. Folding does not delete
                  anything — the recap is written ahead of the day the window has to drop
                  them.
                </template>
                <template v-else>
                  The window holds {{ memoryStatus.window_messages }} of
                  {{ memoryStatus.stored_messages }} stored messages. The rest reach the
                  model only through the recap.
                </template>
              </div>
            </div>

            <div class="grid gap-1">
              <div class="flex flex-wrap items-baseline justify-between gap-2">
                <PSectionLabel as="span" size="sm">Next fold</PSectionLabel>
                <span class="font-mono text-micro tabular-nums">
                  {{ memoryStatus.pending_tokens }} / {{ memoryStatus.fold_batch_tokens }}
                  tokens ({{ foldPercent }}%)
                </span>
              </div>
              <div class="h-2 overflow-hidden rounded-full bg-hairline-soft">
                <div
                  class="h-full rounded-full transition-[width] duration-300"
                  :class="
                    memoryStatus.behind_turns > 0
                      ? 'bg-amber-500'
                      : foldPercent >= 100
                        ? 'bg-emerald-600'
                        : 'bg-sky-600'
                  "
                  :style="{ width: `${Math.min(100, foldPercent)}%` }"
                ></div>
              </div>
              <div class="text-micro text-muted">
                {{ foldState }} · window budget {{ memoryStatus.budget_tokens }} tokens,
                fold line at {{ memoryStatus.high_water_tokens }}
              </div>
            </div>

            <div class="grid gap-1">
              <div class="flex flex-wrap items-baseline justify-between gap-2">
                <PSectionLabel as="span" size="sm">Recap against its share</PSectionLabel>
                <span class="font-mono text-micro tabular-nums">
                  {{ memoryStatus.summary_tokens }} /
                  {{ memoryStatus.summary_budget_tokens }} tokens ({{ recapPercent }}%)
                </span>
              </div>
              <div class="h-2 overflow-hidden rounded-full bg-hairline-soft">
                <div
                  class="h-full rounded-full transition-[width] duration-300"
                  :class="recapPercent > 100 ? 'bg-amber-500' : 'bg-teal-600'"
                  :style="{ width: `${Math.min(100, recapPercent)}%` }"
                ></div>
              </div>
              <div class="text-micro text-muted">
                Covers turn {{ memoryStatus.covers_through_turn }} of
                {{ memoryStatus.turns_total }}. Over its share, the next pass condenses it.
              </div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
            <PButton size="sm" :disabled="store.memoryBusy" @click="onRunSummary">
              {{ store.memoryBusy ? "Running…" : "Run summary now" }}
            </PButton>
            <span class="text-micro text-muted">
              Runs the same pass the background worker runs after a turn. It waits for the
              model, so on a reasoning model it can take a few minutes.
            </span>
          </div>

          <p
            v-if="passReport"
            class="text-micro"
            :class="passFailed ? 'text-warning' : 'text-muted'"
          >
            {{ passReport }}
          </p>

          <div v-if="store.sessionMemory?.summary" class="grid gap-1">
            <div class="text-micro text-muted">
              Story so far — covers {{ store.sessionMemory.summary.covers_through_turn }}
              turn(s), {{ store.sessionMemory.summary.tokens }} tokens, written by
              {{ store.sessionMemory.summary.model_name }} on
              {{ new Date(store.sessionMemory.summary.updated_at).toLocaleString() }}
            </div>
            <p class="whitespace-pre-wrap rounded-control border border-hairline p-2">
              {{ store.sessionMemory.summary.summary }}
            </p>
          </div>
          <p v-else class="text-micro text-muted">
            No recap yet. It is written in the background, once the story passes the fold
            line.
          </p>
        </div>
        <!-- Read-only: directives are set by the player over Telegram (/language, /rule,
             /director), the panel only reflects them. -->
        <div v-show="openPanel === 'directives'">
          <dl class="grid gap-2">
            <div class="flex gap-2">
              <dt class="w-32 shrink-0 text-muted">Language</dt>
              <dd>{{ store.session.directives.language }}</dd>
            </div>
            <div class="flex gap-2">
              <dt class="w-32 shrink-0 text-muted">Scenario rules</dt>
              <dd>
                <span v-if="store.session.directives.rules.length === 0" class="text-muted">
                  None
                </span>
                <ul v-else class="flex flex-col gap-1">
                  <li v-for="rule in store.session.directives.rules" :key="rule.id">
                    <span class="text-muted">{{ rule.id }}.</span> {{ rule.text }}
                  </li>
                </ul>
              </dd>
            </div>
            <div class="flex gap-2">
              <dt class="w-32 shrink-0 text-muted">Director notes</dt>
              <dd>
                <span
                  v-if="store.session.directives.director_instructions.length === 0"
                  class="text-muted"
                >
                  None pending
                </span>
                <!-- Notes stack until a reply consumes them, so all queued ones show. -->
                <ul v-else class="flex flex-col gap-1">
                  <li
                    v-for="(note, index) in store.session.directives.director_instructions"
                    :key="index"
                    class="whitespace-pre-wrap"
                  >
                    <span class="text-muted">{{ index + 1 }}.</span> {{ note }}
                  </li>
                </ul>
              </dd>
            </div>
          </dl>
        </div>
      </PPanel>
    </div>
  </div>
</template>
