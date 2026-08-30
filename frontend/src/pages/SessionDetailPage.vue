<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { PButton, PChip, PPanel, PSectionLabel, PTabs } from "pablo-design-system";

import * as api from "@/api";
import type { AdminMessage, AdminTrace } from "@/api";
import TurnComposer from "@/components/play/TurnComposer.vue";
import { useStickToBottom } from "@/composables/useStickToBottom";
import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ sessionId: string }>();
const store = useAdminStore();
const router = useRouter();

interface MessageFilterState {
  thinking: boolean;
  trace: boolean;
  systemPrompt: boolean;
  turnMeta: boolean;
  // Whether the `···` control is open. It sits with the filters it reveals so that clearing
  // the state on a reload closes the menu too.
  menuOpen: boolean;
}

// Keyed by transcript index — each message's filter checkboxes are independent
// and don't carry over to any other message.
const filterState = reactive<Record<number, MessageFilterState>>({});

function filtersFor(index: number): MessageFilterState {
  let state = filterState[index];
  if (!state) {
    state = {
      thinking: false,
      trace: false,
      systemPrompt: false,
      turnMeta: false,
      menuOpen: false,
    };
    filterState[index] = state;
  }
  return state;
}

async function load(): Promise<void> {
  await store.fetchSessionDetail(props.sessionId);
  // Open on the end of the story, not the beginning of it.
  await scrollToBottom();
}

onMounted(load);
watch(
  () => props.sessionId,
  () => {
    for (const key of Object.keys(filterState)) delete filterState[Number(key)];
    load();
  },
);

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

const backTo = computed(() =>
  store.session ? { name: "user-sessions", params: { userId: store.session.owner_id } } : "/users",
);

async function onDelete(): Promise<void> {
  if (!confirm("Delete this session? This clears its conversation too.")) return;
  await store.deleteSession(props.sessionId);
  router.push(backTo.value);
}

async function onExport(): Promise<void> {
  const exported = await api.exportSession(props.sessionId);
  const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `session-${props.sessionId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

// Last-only deletion. A conversation is an ordered narrative: removing from the middle would
// leave replies answering messages that no longer exist, so undoing a bad stretch means
// peeling from the end. Turn 10 before turn 9.
function isLastMessage(index: number): boolean {
  return index === store.transcript.length - 1;
}

/** What the reader calls each side. `user` / `character` are storage words, not reading ones. */
function roleLabel(message: AdminMessage): string {
  if (message.role === "user") return "you";
  if (message.role === "character") return "narrator";
  return message.role;
}

function messageLabel(message: AdminMessage): string {
  const turn = message.metadata.turn;
  return turn ? `turn ${turn}` : message.role;
}

async function onDeleteLastMessage(message: AdminMessage): Promise<void> {
  if (
    !confirm(
      `Delete the last message (${messageLabel(message)}) and its generation traces? ` +
        "This cannot be undone.",
    )
  ) {
    return;
  }
  // Indices shift when a message goes, so open debug filters would otherwise follow the
  // index onto a different message.
  for (const key of Object.keys(filterState)) delete filterState[Number(key)];
  await store.deleteLastMessage(props.sessionId);
}

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

function tracesForTurn(turn: string | undefined): AdminTrace[] {
  if (!turn) return [];
  return store.traces.filter((trace) => String(trace.record.turn ?? "") === turn);
}

function latestTraceForTurn(turn: string | undefined): AdminTrace | null {
  const matches = tracesForTurn(turn);
  return matches[matches.length - 1] ?? null;
}

function systemPromptFor(turn: string | undefined): string {
  const prompt = latestTraceForTurn(turn)?.record.prompt;
  if (prompt && typeof prompt === "object" && "assembled_system_prompt" in prompt) {
    return String((prompt as Record<string, unknown>).assembled_system_prompt ?? "");
  }
  return "";
}

// --- Playing a turn (S031) ---

const transcriptEl = ref<HTMLElement | null>(null);
const { unseen, measure, settle, scrollToBottom } = useStickToBottom(transcriptEl);
const draft = ref("");

const pending = computed(() => store.pendingTurn);
const generating = computed(() => store.isGenerating);
const isRetired = computed(() => Boolean(store.session?.deleted_at));

const lastMessage = computed(() => store.transcript[store.transcript.length - 1] ?? null);

// Retry replaces a narrator reply, so there has to be one. The service refuses anything else
// and says why; this only decides whether to offer the item.
const canRetry = computed(() => lastMessage.value?.role === "character");

// The last reply stopped at the token cap, so Continue would finish that sentence in place
// rather than advance. Costs nothing to know: the finish reason is already on the message.
const finishesReply = computed(
  () =>
    lastMessage.value?.role === "character" &&
    lastMessage.value.metadata.finish_reason === "length",
);

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

// A new turn arrived. `sync` so this runs before the DOM is patched — the scroll position
// still describes the transcript as the reader last saw it, which is the only moment the
// "was I following?" question has a true answer.
watch(
  () => store.transcript.length,
  (next, previous) => {
    // `previous === 0` is the first load, which `load()` already scrolled. A shorter list is
    // a delete, not a new turn.
    if (previous === 0 || next <= previous) return;
    void settle(measure());
  },
  { flush: "sync" },
);

async function onSend(message: string): Promise<void> {
  // The player just acted, so they are following by definition.
  await scrollToBottom();
  const ok = await store.playTurn(props.sessionId, message);
  // Only a send that worked clears the box. A refused turn leaves what was typed.
  if (ok) draft.value = "";
}

async function onContinue(): Promise<void> {
  await scrollToBottom();
  await store.playContinue(props.sessionId);
}

async function onRetry(): Promise<void> {
  await scrollToBottom();
  await store.playRetry(props.sessionId);
}

/** Whether this turn recorded anything the `···` could show.
 *
 * Turns written before S012/S022 carry no `turn` in their metadata, and the trace lookup is
 * by turn number — so for those the drawer opens onto four checkboxes that each answer
 * "nothing recorded". Say that on the control instead of behind it.
 */
function hasThinking(message: AdminMessage): boolean {
  return Boolean(message.metadata.thinking);
}

function hasTrace(message: AdminMessage): boolean {
  return tracesForTurn(message.metadata.turn).length > 0;
}

function hasSystemPrompt(message: AdminMessage): boolean {
  return systemPromptFor(message.metadata.turn) !== "";
}

function hasAnyDebug(message: AdminMessage): boolean {
  return hasThinking(message) || hasTrace(message);
}

function debugOpen(index: number): boolean {
  return filtersFor(index).menuOpen;
}

async function toggleDebug(index: number, event: MouseEvent): Promise<void> {
  const state = filtersFor(index);
  state.menuOpen = !state.menuOpen;
  if (!state.menuOpen) return;
  // The row opens *below* the message, and the message is usually the last one in a short
  // scroll box — so the thing that just appeared is off-screen and the click reads as doing
  // nothing. Bring it back into view once it exists.
  await nextTick();
  // Target the revealed row, not the message. A long narrator turn is taller than the scroll
  // box, so the browser already counts the `li` as "in view" and `nearest` moves nothing —
  // which is exactly the bug: the options open 500px below the fold and the click looks dead.
  const row = (event.currentTarget as HTMLElement | null)
    ?.closest("li")
    ?.querySelector("[data-debug-row]");
  row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function turnMetaFor(turn: string | undefined): Record<string, unknown> {
  const trace = latestTraceForTurn(turn);
  if (!trace) return {};
  return {
    finish_reason: trace.record.finish_reason,
    latency_ms: trace.record.latency_ms,
    usage: trace.record.usage,
  };
}
</script>

<template>
  <div>
    <RouterLink :to="backTo" class="text-body text-muted">&larr; Sessions</RouterLink>

    <p v-if="store.sessionLoading" class="mt-2 text-body text-muted">Loading…</p>
    <p v-else-if="store.sessionError" class="mt-2 text-body text-danger">
      {{ store.sessionError }}
    </p>

    <template v-else-if="store.session">
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
          <PButton size="sm" @click="onExport">Export</PButton>
          <PButton size="sm" variant="danger" @click="onDelete">Delete</PButton>
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
        <!-- Editable here, but only here: /clear is still the only way a *player* can change
             their character. An admin sees the whole session, so they can correct one. -->
        <form v-if="canEditPersona" class="grid gap-2" @submit.prevent="onSavePersona">
          <p v-if="!hasPersona" class="text-micro text-muted">
            <!-- v-pre: the placeholder is literal text, not an interpolation. -->
            This session has no persona, so <code v-pre>{{user}}</code> falls back to the
            player's Telegram name.
          </p>
          <p v-else class="text-micro text-muted">
            The player cannot change this themselves — /clear starts a fresh session instead.
            Renaming re-renders past turns under the new name.
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
          No persona, and this session was superseded — a persona set here would never reach
          a prompt.
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
            <!-- Categorical, not semantic: three fixed colours distinguish recap / pending /
                 verbatim, none of which is "the accent" or "a warning". No token in the
                 package models that, so these three stay literal on purpose (S032 audit). -->
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
                Every stored turn still reaches the prompt. Folding does not delete anything —
                the recap is written ahead of the day the window has to drop them.
              </template>
              <template v-else>
                The window holds {{ memoryStatus.window_messages }} of
                {{ memoryStatus.stored_messages }} stored messages. The rest reach the model
                only through the recap.
              </template>
            </div>
          </div>

          <div class="grid gap-1">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <PSectionLabel as="span" size="sm">Next fold</PSectionLabel>
              <span class="font-mono text-micro tabular-nums">
                {{ memoryStatus.pending_tokens }} / {{ memoryStatus.fold_batch_tokens }} tokens
                ({{ foldPercent }}%)
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
              {{ foldState }} · window budget {{ memoryStatus.budget_tokens }} tokens, fold line
              at {{ memoryStatus.high_water_tokens }}
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
            Story so far — covers {{ store.sessionMemory.summary.covers_through_turn }} turn(s),
            {{ store.sessionMemory.summary.tokens }} tokens, written by
            {{ store.sessionMemory.summary.model_name }} on
            {{ new Date(store.sessionMemory.summary.updated_at).toLocaleString() }}
          </div>
          <p class="whitespace-pre-wrap rounded-control border border-hairline p-2">
            {{ store.sessionMemory.summary.summary }}
          </p>
        </div>
        <p v-else class="text-micro text-muted">
          No recap yet. It is written in the background, once the story passes the fold line.
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

      <p
        v-if="store.actionError"
        class="mb-3 rounded-control border border-danger bg-danger-soft px-3 py-2 text-body text-danger"
      >
        {{ store.actionError }}
      </p>

      <div class="relative">
        <!-- The scroll well's tint is deliberately not a token: it's a recessed area, not a
             surface or a panel, and no token in the package models "recessed" (S032 audit). -->
        <div
          ref="transcriptEl"
          class="h-[calc(100vh-20rem)] min-h-[15rem] overflow-y-auto rounded-panel border border-hairline-soft bg-ground px-3 py-3"
        >
          <p v-if="store.transcript.length === 0 && !pending" class="p-2 text-body text-muted">
            No messages yet.
          </p>
      <ol class="flex flex-col gap-5">
        <li
          v-for="(message, index) in store.transcript"
          :key="index"
          class="group rounded-control px-4 py-3"
          :class="
            message.role === 'user'
              ? 'ml-3 bg-accent-soft sm:ml-6'
              : 'mr-3 border border-hairline-soft bg-surface sm:mr-6'
          "
        >
          <div
            class="mb-1.5 flex items-center gap-2 text-micro font-semibold uppercase tracking-wider text-muted"
          >
            <span>{{ roleLabel(message) }}</span>
            <span v-if="message.metadata.turn">&middot; turn {{ message.metadata.turn }}</span>
            <span class="ml-auto flex items-center gap-2 normal-case">
              <!-- Only the final message is deletable, which is what enforces the ordering. -->
              <PButton
                v-if="isLastMessage(index)"
                variant="danger"
                size="sm"
                title="Delete this message. Only the last message can be deleted."
                @click="onDeleteLastMessage(message)"
              >
                Delete last
              </PButton>
            </span>
          </div>
          <div
            class="whitespace-pre-wrap text-prose"
            :class="message.role === 'character' ? 'font-display' : ''"
          >
            {{ message.content }}
          </div>

          <template v-if="message.role === 'character'">
            <!-- Named, and placed where its content will appear. A `···` in the header was
                 two guesses: what it does, and where the answer will show up. -->
            <button
              type="button"
              :disabled="!hasAnyDebug(message)"
              class="mt-3 -mb-1 flex items-center gap-1.5 rounded text-micro font-medium uppercase tracking-wider text-muted enabled:hover:text-ink disabled:cursor-default disabled:opacity-60"
              :aria-expanded="debugOpen(index)"
              @click="toggleDebug(index, $event)"
            >
              <span aria-hidden="true" class="text-[9px]">{{ debugOpen(index) ? "▾" : "▸" }}</span>
              <span v-if="!hasAnyDebug(message)">No admin data for this turn</span>
              <span v-else>{{ debugOpen(index) ? "Hide" : "Show" }} admin actions</span>
            </button>

            <div
              v-if="debugOpen(index)"
              data-debug-row
              class="mt-2 flex scroll-mb-24 flex-wrap gap-3 border-t border-hairline pt-2 text-micro text-muted"
            >
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasThinking(message) }"
                :title="hasThinking(message) ? '' : 'No thinking captured for this turn.'"
              >
                <input
                  v-model="filtersFor(index).thinking"
                  type="checkbox"
                  :disabled="!hasThinking(message)"
                />
                Thinking
              </label>
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasTrace(message) }"
                :title="hasTrace(message) ? '' : 'No trace recorded for this turn.'"
              >
                <input
                  v-model="filtersFor(index).trace"
                  type="checkbox"
                  :disabled="!hasTrace(message)"
                />
                Raw trace
              </label>
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasSystemPrompt(message) }"
                :title="hasSystemPrompt(message) ? '' : 'No system prompt recorded for this turn.'"
              >
                <input
                  v-model="filtersFor(index).systemPrompt"
                  type="checkbox"
                  :disabled="!hasSystemPrompt(message)"
                />
                System prompt
              </label>
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasTrace(message) }"
                :title="hasTrace(message) ? '' : 'No trace recorded for this turn.'"
              >
                <input
                  v-model="filtersFor(index).turnMeta"
                  type="checkbox"
                  :disabled="!hasTrace(message)"
                />
                Turn metadata
              </label>
            </div>

            <div
              v-if="filtersFor(index).thinking"
              class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-control bg-warning-soft p-2 text-micro"
            >
              {{ message.metadata.thinking }}
            </div>

            <div
              v-if="filtersFor(index).systemPrompt"
              class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-control bg-raised p-2 text-micro"
            >
              {{ systemPromptFor(message.metadata.turn) || "No system prompt recorded for this turn." }}
            </div>

            <div
              v-if="filtersFor(index).turnMeta"
              class="mt-2 overflow-x-auto rounded-control bg-raised p-2 text-micro"
            >
              <pre>{{ JSON.stringify(turnMetaFor(message.metadata.turn), null, 2) }}</pre>
            </div>

            <div
              v-if="filtersFor(index).trace"
              class="mt-2 overflow-x-auto rounded-control bg-raised p-2 text-micro"
            >
              <template v-if="tracesForTurn(message.metadata.turn).length > 0">
                <pre
                  v-for="(trace, traceIndex) in tracesForTurn(message.metadata.turn)"
                  :key="traceIndex"
                  >{{ JSON.stringify(trace.record, null, 2) }}</pre
                >
              </template>
              <span v-else class="text-muted">No trace recorded for this turn.</span>
            </div>
          </template>
        </li>
      </ol>

          <!-- The turn in flight. It is drawn here rather than pushed into `transcript`,
               which stays the server's list and nothing else. -->
          <div v-if="pending" class="mt-5 flex flex-col gap-5">
            <!-- Bubble tint matches the mockup: the accent-soft "you" tint and the plain
                 surface/hairline narrator bubble, same as the transcript above. -->
            <div v-if="pending.message" class="ml-3 rounded-control bg-accent-soft px-4 py-3 sm:ml-6">
              <div class="mb-1.5 text-micro font-semibold uppercase tracking-wider text-muted">
                you
              </div>
              <div class="whitespace-pre-wrap text-prose">
                {{ pending.message }}
              </div>
            </div>
            <div
              class="mr-3 rounded-control px-4 py-3 sm:mr-6"
              :class="pending.error ? 'bg-danger-soft' : 'border border-hairline-soft bg-surface'"
            >
              <template v-if="pending.error">
                <div class="mb-1.5 text-micro font-semibold uppercase tracking-wider text-danger">
                  not sent
                </div>
                <div class="text-prose text-danger">
                  {{ pending.error }}
                </div>
                <PButton size="sm" class="mt-2" @click="store.clearPendingTurn()">
                  Dismiss
                </PButton>
              </template>
              <template v-else>
                <div class="mb-1.5 text-micro font-semibold uppercase tracking-wider text-muted">
                  narrator
                </div>
                <div class="flex items-center gap-2 font-display text-prose italic text-muted">
                  <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted"></span>
                  writing…
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Only while the reader is away from the newest turn. Following, there is nothing
             to jump to. Not PButton: this wants an inverted-contrast floating affordance
             (dark pill on light, light pill on dark), which `bg-ink`/`text-ground` gives for
             free -- both tokens already flip per theme, mirroring the mockup's pill exactly. -->
        <div v-if="unseen > 0" class="pointer-events-none absolute inset-x-0 bottom-2 flex justify-center">
          <button
            type="button"
            class="pointer-events-auto rounded-full bg-ink px-3 py-1 text-micro font-medium text-ground shadow-lg"
            @click="scrollToBottom(true)"
          >
            &darr; {{ unseen }} new
          </button>
        </div>
      </div>

      <div class="mt-3">
        <TurnComposer
          v-model="draft"
          :generating="generating"
          :disabled="isRetired"
          :can-retry="canRetry"
          :finishes-reply="finishesReply"
          retry-reason="the last message is not a narrator reply"
          @send="onSend"
          @continue-story="onContinue"
          @retry="onRetry"
        />
      </div>
    </template>
  </div>
</template>
